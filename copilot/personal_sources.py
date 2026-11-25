"""Public, keyword-directed discovery. Conference labels require structured source metadata."""
import re
from datetime import timedelta

from .ingest import arxiv_id, fresh, normalize_doi, parse_atom, upsert_paper

LATEST_HOURS = 72
ARCHIVE_DAYS = 90
CONFERENCE_YEARS = 5
KEYWORD_ALIASES = {
    "大语言模型": ["large language model", "LLM"],
    "大模型": ["large language model", "LLM"],
    "智能体": ["agent"],
    "多智能体": ["multi agent", "multi-agent"],
    "检索增强生成": ["retrieval augmented generation", "RAG"],
    "模型评测": ["model evaluation", "benchmark"],
    "强化学习": ["reinforcement learning"],
    "联邦学习": ["federated learning"],
    "分布式训练": ["distributed training"],
    "多模态": ["multimodal"],
    "计算机视觉": ["computer vision"],
    "自然语言处理": ["natural language processing", "NLP"],
    "机器学习": ["machine learning"],
    "深度学习": ["deep learning"],
}


def keyword_variants(word):
    return [word, *KEYWORD_ALIASES.get(word.strip(), [])]


VENUES = {
    "NeurIPS": ["neurips", "nips", "neural information processing systems"],
    "ICML": ["icml", "international conference on machine learning"],
    "ICLR": ["iclr", "international conference on learning representations"],
    "ACL": ["acl", "annual meeting of the association for computational linguistics"],
    "EMNLP": ["emnlp", "empirical methods in natural language processing"],
    "NAACL": ["naacl", "north american chapter of the association for computational linguistics"],
    "CVPR": ["cvpr", "computer vision and pattern recognition"],
    "ICCV": ["iccv", "international conference on computer vision"],
    "ECCV": ["eccv", "european conference on computer vision"],
    "AAAI": ["aaai", "aaai conference on artificial intelligence"],
    "IJCAI": ["ijcai", "international joint conference on artificial intelligence"],
    "KDD": ["kdd", "knowledge discovery and data mining"],
    "SIGIR": ["sigir", "research and development in information retrieval"],
    "WWW": ["www", "the web conference", "international world wide web conference"],
}


def conference_name(item):
    publication = item.get("publicationVenue") or {}
    values = [value for value in [item.get("venue"), publication.get("name"),
              *(publication.get("alternate_names") or [])] if isinstance(value, str)]
    kinds = item.get("publicationTypes") or []
    if kinds and "Conference" not in kinds:
        return None
    # Findings, workshops and companion volumes are not promoted into main conference papers.
    for value in values:
        value = re.sub(r"[^\w]+", " ", value.casefold()).strip()
        if any(term in value for term in ("workshop", "findings", "companion", "demonstration", "arxiv")):
            return None
    for canonical, aliases in VENUES.items():
        for value in values:
            normalized = " " + re.sub(r"[^\w]+", " ", value.casefold()).strip() + " "
            if any(" " + alias + " " in normalized for alias in aliases):
                return canonical
    return None


def conference_record(item, now):
    venue = conference_name(item)
    year, sid = item.get("year"), item.get("paperId")
    if not venue or not isinstance(year, int) or not now.year - CONFERENCE_YEARS + 1 <= year <= now.year:
        return None
    if not isinstance(sid, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", sid) or not item.get("title"):
        return None
    external = item.get("externalIds") or {}
    base = version = None
    if external.get("ArXiv"):
        try:
            base, version = arxiv_id(external["ArXiv"])
        except ValueError:
            pass
    source = f"https://www.semanticscholar.org/paper/{sid}"
    return {
        "s2_id": sid, "arxiv_id": base, "arxiv_version": version,
        "doi": normalize_doi(external.get("DOI")),
        "title": item["title"], "abstract": item.get("abstract") or "",
        "authors": [author["name"] for author in (item.get("authors") or [])
                    if isinstance(author, dict) and author.get("name")],
        "categories": [], "first_date_verified": False,
        "source_url": f"https://arxiv.org/abs/{base}" if base else source,
        "code_urls": [], "venue": venue, "publication_year": year, "venue_source": source,
    }


def openalex_conference_record(item, now):
    location = item.get("primary_location") or {}
    if location.get("raw_type") != "proceedings-article":
        return None
    venue = conference_name({"venue": (location.get("source") or {}).get("display_name")})
    year, work_id = item.get("publication_year"), str(item.get("id", ""))
    if not venue or not isinstance(year, int) or not now.year - CONFERENCE_YEARS + 1 <= year <= now.year:
        return None
    title = item.get("display_name")
    if not title or not re.fullmatch(r"https://openalex\.org/W\d+", work_id):
        return None
    identifiers = item.get("ids") or {}
    doi = normalize_doi(item.get("doi"))
    arxiv = identifiers.get("arxiv") or (doi.removeprefix("10.48550/arxiv.") if doi and
                                         doi.startswith("10.48550/arxiv.") else "")
    try:
        base, version = arxiv_id(arxiv)
    except ValueError:
        base = version = None
    words = {}
    for word, positions in (item.get("abstract_inverted_index") or {}).items():
        for position in positions:
            if isinstance(position, int) and 0 <= position < 3500:
                words[position] = word
    return {
        "title": title, "abstract": " ".join(words[index] for index in sorted(words)),
        "authors": [name for author in item.get("authorships") or []
                    if (name := (author.get("author") or {}).get("display_name"))],
        "doi": doi, "arxiv_id": base, "arxiv_version": version, "categories": [],
        "first_date_verified": False, "source_url": f"https://arxiv.org/abs/{base}" if base else work_id,
        "code_urls": [], "venue": venue, "publication_year": year, "venue_source": work_id,
    }


def discover_personal(fetch, team_id, preferences, now):
    keywords = list(dict.fromkeys(variant for word in preferences.keywords for variant in keyword_variants(word)))
    # Quoting prevents user keywords from changing the public APIs' Boolean query structure.
    clean = [re.sub(r'["\\|+()~:*<>]', " ", word).strip() for word in keywords]
    clean = [word for word in clean if word]
    if not clean:
        return ["方向关键词不包含可检索文字"], []
    warnings, records = [], []
    # Query a larger window once. Selection still marks only the last 72 hours as latest.
    if preferences.conference_ratio < 1:
        since = now - timedelta(days=ARCHIVE_DAYS)
        query = " OR ".join(f'(ti:"{word}" OR abs:"{word}")' for word in clean)
        upper = now.replace(minute=59, second=0, microsecond=0)
        lower = since.replace(minute=0, second=0, microsecond=0)
        try:
            body = fetch.get("https://export.arxiv.org/api/query", {
                "search_query": f"({query}) AND submittedDate:[{lower:%Y%m%d%H%M} TO {upper:%Y%m%d%H%M}]",
                "start": 0, "max_results": 100, "sortBy": "submittedDate", "sortOrder": "descending"})
            records.extend(record for record in parse_atom(body) if fresh(record, since, now))
        except Exception:
            warnings.append("最新论文来源暂不可用，已尝试复用现有候选")
    if preferences.conference_ratio > 0:
        conference = []
        try:
            data = fetch.json("https://api.semanticscholar.org/graph/v1/paper/search/bulk", {
                "query": " | ".join(f'"{word}"' for word in clean),
                "venue": ",".join(VENUES),
                "publicationTypes": "Conference",
                "year": f"{now.year - CONFERENCE_YEARS + 1}-{now.year}",
                "sort": "publicationDate:desc",
                "fields": "title,abstract,authors,year,venue,publicationVenue,publicationTypes,externalIds",
            })
            for item in (data.get("data") or [])[:200]:
                record = conference_record(item, now)
                if record:
                    conference.append(record)
        except Exception:
            warnings.append("Semantic Scholar 暂不可用")
        if len(conference) < preferences.paper_count * preferences.conference_ratio:
            try:
                data = fetch.json("https://api.openalex.org/works", {
                    "search": " OR ".join(f'"{word}"' for word in clean),
                    "filter": f"primary_location.raw_type:proceedings-article,from_publication_date:{now.year - CONFERENCE_YEARS + 1}-01-01",
                    "per_page": 50,
                    "select": "id,ids,doi,display_name,publication_year,primary_location,authorships,abstract_inverted_index",
                })
                for item in (data.get("results") or []):
                    record = openalex_conference_record(item, now)
                    if record:
                        conference.append(record)
            except Exception:
                warnings.append("OpenAlex 顶会检索暂不可用，已尝试复用现有候选")
        records.extend(conference)
    ids = []
    for record in records:
        try:
            paper_id, _ = upsert_paper(record, [team_id])
            ids.append(paper_id)
        except Exception:
            warnings.append("部分候选入库失败")
    return list(dict.fromkeys(warnings)), ids

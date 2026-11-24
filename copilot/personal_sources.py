"""Public, keyword-directed discovery. Conference labels require structured source metadata."""
import re
from datetime import timedelta

from .ingest import arxiv_id, fresh, normalize_doi, parse_atom, upsert_paper

LATEST_HOURS = 72
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
    values = [item.get("venue", ""), publication.get("name", ""), *(publication.get("alternate_names") or [])]
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
        "authors": [author.get("name", "") for author in item.get("authors", [])],
        "categories": [], "first_date_verified": False,
        "source_url": f"https://arxiv.org/abs/{base}" if base else source,
        "code_urls": [], "venue": venue, "publication_year": year, "venue_source": source,
    }


def discover_personal(fetch, team_id, preferences, now):
    keywords = list(dict.fromkeys(variant for word in preferences.keywords for variant in keyword_variants(word)))
    # Quoting prevents user keywords from changing the public APIs' Boolean query structure.
    clean = [re.sub(r'["\\|+()~:*<>]', " ", word).strip() for word in keywords]
    clean = [word for word in clean if word]
    if not clean:
        return ["方向关键词不包含可检索文字"], []
    warnings, records = [], []
    if preferences.conference_ratio < 1:
        since = now - timedelta(hours=LATEST_HOURS)
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
        try:
            data = fetch.json("https://api.semanticscholar.org/graph/v1/paper/search/bulk", {
                "query": " | ".join(f'"{word}"' for word in clean),
                "venue": ",".join(VENUES),
                "publicationTypes": "Conference",
                "year": f"{now.year - CONFERENCE_YEARS + 1}-{now.year}",
                "sort": "publicationDate:desc",
                "fields": "title,abstract,authors,year,venue,publicationVenue,publicationTypes,externalIds",
            })
            for item in data.get("data", [])[:200]:
                record = conference_record(item, now)
                if record:
                    records.append(record)
        except Exception:
            warnings.append("顶会论文来源暂不可用，已尝试复用现有候选")
    ids = []
    for record in records:
        try:
            paper_id, _ = upsert_paper(record, [team_id])
            ids.append(paper_id)
        except Exception:
            warnings.append("部分候选入库失败")
    return list(dict.fromkeys(warnings)), ids

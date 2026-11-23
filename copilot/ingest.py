import logging
import re
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import unquote

from defusedxml import ElementTree
from sqlalchemy import select

from .config import settings
from .db import lock, session
from .fetch import Fetcher
from .models import Paper, TeamPaper

log = logging.getLogger(__name__)
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
ID_RE = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$")


def arxiv_id(value: str) -> tuple[str, str]:
    value = unquote(value).strip().split("/abs/")[-1].removesuffix(".pdf")
    if not ID_RE.fullmatch(value):
        raise ValueError("Invalid arXiv identifier")
    return re.sub(r"v\d+$", "", value), value


def normalize_title(value: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", unicodedata.normalize("NFKC", value).lower()).split())


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.IGNORECASE)
    return value.lower()


def parse_atom(body: bytes) -> list[dict]:
    result = []
    for entry in ElementTree.fromstring(body).findall(f"{ATOM}entry"):
        base, version = arxiv_id(entry.findtext(f"{ATOM}id", ""))
        abstract = " ".join(entry.findtext(f"{ATOM}summary", "").split())
        result.append({
            "arxiv_id": base, "arxiv_version": version,
            "title": " ".join(entry.findtext(f"{ATOM}title", "").split()), "abstract": abstract,
            "authors": [a.findtext(f"{ATOM}name", "") for a in entry.findall(f"{ATOM}author")],
            "categories": [a.attrib["term"] for a in entry.findall(f"{ATOM}category")],
            "doi": normalize_doi(entry.findtext(f"{ARXIV}doi")),
            "first_submitted_at": datetime.fromisoformat(entry.findtext(f"{ATOM}published").replace("Z", "+00:00")),
            "updated_at": datetime.fromisoformat(entry.findtext(f"{ATOM}updated").replace("Z", "+00:00")),
            "first_date_verified": True, "source_url": f"https://arxiv.org/abs/{base}",
            "code_urls": sorted(set(re.findall(r"https://github\.com/[\w.-]+/[\w.-]+", abstract))),
        })
    return result


def fresh(paper: dict, since: datetime, until: datetime) -> bool:
    first = paper.get("first_submitted_at")
    return bool(paper.get("first_date_verified") and first and since <= first <= until)


def upsert_paper(data: dict, team_ids: list) -> tuple[str, bool]:
    data["normalized_title"] = normalize_title(data["title"])
    with session() as db:
        lock(db, "paper-dedup")
        existing = None
        for key in ("arxiv_id", "doi", "s2_id"):
            if data.get(key):
                existing = db.scalar(select(Paper).where(getattr(Paper, key) == data[key]))
                if existing:
                    break
        if not existing:
            exact = db.scalars(select(Paper).where(Paper.normalized_title == data["normalized_title"])).all()
            existing = next((p for p in exact if not (
                p.arxiv_id and data.get("arxiv_id") and p.arxiv_id != data["arxiv_id"])), None)
        # Fuzzy title matching is a conservative last resort; conflicting arXiv IDs are never merged.
        if not existing:
            prefix = data["normalized_title"].split()[:3]
            candidates = db.scalars(select(Paper).where(
                Paper.normalized_title.startswith(" ".join(prefix), autoescape=True)).limit(50)).all()
            for candidate in candidates:
                conflict = (candidate.arxiv_id and data.get("arxiv_id") and
                            candidate.arxiv_id != data["arxiv_id"])
                if not conflict and SequenceMatcher(None, candidate.normalized_title,
                                                   data["normalized_title"]).ratio() >= .97:
                    existing = candidate
                    break
        created = existing is None
        if created:
            existing = Paper(**data)
            db.add(existing)
            db.flush()
        else:
            # Keep the earliest verified submission, never replace with an updated/publication timestamp.
            if data.get("first_date_verified"):
                old = existing.first_submitted_at
                existing.first_submitted_at = min(old, data["first_submitted_at"]) if old else data["first_submitted_at"]
                existing.first_date_verified = True
            newer = not existing.updated_at or (data.get("updated_at") and data["updated_at"] >= existing.updated_at)
            if newer:
                for key in ("abstract", "arxiv_version", "updated_at", "code_urls"):
                    if data.get(key):
                        setattr(existing, key, data[key])
            for key in ("doi", "s2_id", "arxiv_id"):
                if data.get(key) and not getattr(existing, key):
                    setattr(existing, key, data[key])
        for team_id in team_ids:
            if not db.get(TeamPaper, (team_id, existing.id)):
                db.add(TeamPaper(team_id=team_id, paper_id=existing.id))
        return str(existing.id), created


def collect(fetch: Fetcher, team_ids: list, now: datetime, hours: int = 72, limit: int = 200) -> dict:
    since = now - timedelta(hours=hours)
    categories = " OR ".join(f"cat:{x}" for x in settings().arxiv_categories)
    date_range = f"submittedDate:[{since:%Y%m%d%H%M} TO {now:%Y%m%d%H%M}]"
    candidates, warnings = {}, []
    for start in range(0, limit, 100):
        body = fetch.get("https://export.arxiv.org/api/query", params={
            "search_query": f"({categories}) AND {date_range}", "start": start,
            "max_results": min(100, limit - start), "sortBy": "submittedDate", "sortOrder": "descending"})
        items = parse_atom(body)
        for item in items:
            if fresh(item, since, now):
                candidates[item["arxiv_id"]] = item
        if len(items) < min(100, limit - start):
            break
    discovered_ids = set()
    if settings().enable_hf:
        try:
            for item in fetch.json("https://huggingface.co/api/daily_papers", {"limit": 100}):
                raw = item.get("paper", {}).get("id", "")
                try:
                    discovered_ids.add(arxiv_id(raw)[0])
                except ValueError:
                    continue
        except Exception as exc:
            warnings.append(f"hf:{type(exc).__name__}")
    # Semantic Scholar enriches discovery; publicationDate is never accepted as first submission.
    try:
        data = fetch.json("https://api.semanticscholar.org/graph/v1/paper/search/bulk", {
            "query": "large language model | retrieval augmented generation | agent",
            "publicationDateOrYear": f"{since:%Y-%m-%d}:{now:%Y-%m-%d}",
            "fields": "paperId,title,externalIds,publicationDate", "sort": "publicationDate:desc"})
        for item in data.get("data", [])[:100]:
            raw = (item.get("externalIds") or {}).get("ArXiv")
            if raw:
                try:
                    discovered_ids.add(arxiv_id(raw)[0])
                except ValueError:
                    continue
    except Exception as exc:
        warnings.append(f"s2:{type(exc).__name__}")
    missing = sorted(discovered_ids - candidates.keys())[:100]
    for start in range(0, len(missing), 25):
        try:
            body = fetch.get("https://export.arxiv.org/api/query", {
                "id_list": ",".join(missing[start:start + 25]), "max_results": 25})
            for item in parse_atom(body):
                if fresh(item, since, now):
                    candidates[item["arxiv_id"]] = item
        except Exception as exc:
            warnings.append(f"crosscheck:{type(exc).__name__}")
    created = 0
    for item in list(candidates.values())[:limit]:
        try:
            _, was_created = upsert_paper(item, team_ids)
            created += was_created
        except Exception as exc:
            warnings.append(f"upsert:{type(exc).__name__}")
    return {"verified_candidates": min(len(candidates), limit), "new_papers": created, "warnings": warnings}

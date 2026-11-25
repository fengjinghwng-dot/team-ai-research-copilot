"""Work-specific author affiliations from public metadata."""
import re
from urllib.parse import quote

from .fetch import Fetcher, FetchError
from .ingest import arxiv_id, normalize_doi


def paper_affiliations(paper):
    identifiers = [normalize_doi(paper.doi)]
    if paper.arxiv_id:
        identifiers.append(f"10.48550/arxiv.{paper.arxiv_id}".lower())
    dois = dict.fromkeys(doi for doi in identifiers if doi and re.fullmatch(r"10\.\d{4,9}/\S+", doi))
    fetch = Fetcher(attempts=1, timeout=8)
    unavailable = False
    for doi in dois:
        try:
            work = fetch.json(
                f"https://api.openalex.org/works/https://doi.org/{quote(doi, safe='/')}",
                {"select": "id,ids,doi,authorships"},
            )
        except FetchError as exc:
            unavailable |= str(exc) != "Source request failed: 404"
            continue
        except ValueError:
            unavailable = True
            continue
        if not isinstance(work, dict):
            continue
        ids = work.get("ids") or {}
        matched = normalize_doi(work.get("doi")) == doi
        if not matched and doi.startswith("10.48550/arxiv.") and ids.get("arxiv"):
            try:
                matched = arxiv_id(ids["arxiv"])[0].lower() == doi.removeprefix("10.48550/arxiv.")
            except ValueError:
                pass
        if not matched:
            continue
        items = []
        for authorship in work.get("authorships") or []:
            names = [institution.get("display_name") for institution in authorship.get("institutions") or []]
            if not any(names):
                names = authorship.get("raw_affiliation_strings") or []
            institutions = list(dict.fromkeys(name.strip() for name in names if isinstance(name, str) and name.strip()))
            author = (authorship.get("author") or {}).get("display_name") or authorship.get("raw_author_name")
            if author and institutions:
                items.append({"author": author, "institutions": institutions})
        if items:
            work_id = str(work.get("id", "")).removeprefix("https://openalex.org/")
            source_url = f"https://openalex.org/{work_id}" if re.fullmatch(r"W\d+", work_id) else None
            return {"state": "available", "items": items, "source_url": source_url}
    return {"state": "unavailable" if unavailable else "not_listed", "items": [], "source_url": None}

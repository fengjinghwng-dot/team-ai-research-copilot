import gzip
import hashlib
import io
import logging
import tarfile

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .db import session
from .fetch import Fetcher
from .ingest import arxiv_id
from .models import Document, Paper

log = logging.getLogger(__name__)
PARSER_VERSION = "anchors-v2"
MAX_CHARS = 90_000


def trim_sections(sections: dict) -> tuple[dict, bool]:
    result, remaining, truncated = {}, MAX_CHARS, False
    for anchor, text in sections.items():
        text = " ".join(text.split())
        if not text:
            continue
        if len(text) > remaining:
            truncated = True
        if remaining > 0:
            result[anchor] = text[:remaining]
            remaining -= len(result[anchor])
    return result, truncated


def html_sections(body: bytes) -> dict:
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    sections = {}
    # Paragraph-level stable anchors preserve formula alt text and table text where available.
    for i, tag in enumerate(soup.select("p, table, h1, h2, h3, h4, .ltx_equation")):
        parent = tag.find_parent(attrs={"id": True})
        anchor = tag.get("id") or (parent.get("id") if parent else f"block-{i}")
        for math in tag.select("math"):
            math.replace_with(math.get("alttext") or math.get_text(" ", strip=True))
        text = tag.get_text(" ", strip=True)
        sections[anchor] = (sections.get(anchor, "") + " " + text).strip()
    return sections


def latex_sections(body: bytes) -> dict:
    sections, total = {}, 0
    try:
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:*") as archive:
            for member in archive:
                # Read into memory; never extract files or follow archive links.
                if not member.isfile() or not member.name.endswith(".tex") or member.size > 2_000_000:
                    continue
                if total + member.size > 6_000_000:
                    break
                source = archive.extractfile(member)
                if source:
                    sections[f"latex:{member.name}"] = source.read().decode("utf-8", errors="replace")
                    total += member.size
    except tarfile.ReadError:
        if body.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as source:
                raw = source.read(6_000_001)
        else:
            raw = body
        if len(raw) > 6_000_000:
            raise ValueError("LaTeX decompression limit exceeded")
        text = raw.decode("utf-8", errors="replace")
        if '\\documentclass' in text or '\\begin{document}' in text:
            sections["latex:main"] = text
    return sections


def pdf_sections(body: bytes) -> dict:
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) > 150:
        raise ValueError("PDF exceeds page limit")
    return {f"page-{i + 1}": page.extract_text() or "" for i, page in enumerate(reader.pages)}


def fulltext(paper: Paper, fetch: Fetcher) -> Document | None:
    if not paper.arxiv_id:
        return None
    _, version = arxiv_id(paper.arxiv_version or paper.arxiv_id)
    cache_key = hashlib.sha256(f"{version}:{paper.updated_at}:{PARSER_VERSION}".encode()).hexdigest()
    with session() as db:
        cached = db.get(Document, cache_key)
        if cached:
            return cached
    methods = [("html", f"https://arxiv.org/html/{version}", html_sections),
               ("latex", f"https://arxiv.org/src/{version}", latex_sections),
               ("pdf", f"https://arxiv.org/pdf/{version}", pdf_sections)]
    for kind, url, parser in methods:
        try:
            sections, truncated = trim_sections(parser(fetch.get(url, permanent="v" in version[-4:])))
            if sum(len(x) for x in sections.values()) < 1000:
                continue
            with session() as db:
                # Another worker may have fetched this document in the meantime.
                cached = db.get(Document, cache_key)
                if cached:
                    return cached
                doc = Document(cache_key=cache_key, paper_id=paper.id, kind=kind,
                               sections=sections, truncated=truncated)
                db.add(doc)
                db.flush()
                return doc
        except Exception as exc:
            log.warning("fulltext fallback paper=%s source=%s error=%s", paper.id, kind, type(exc).__name__)
    return None

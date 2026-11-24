import hashlib
import json
from pathlib import Path

from sqlalchemy import select, text

from . import llm
from .budget import BudgetExceeded
from .config import settings
from .db import lock, session
from .fetch import Fetcher
from .llm import LLMDisabled
from .models import Analysis, Paper
from .parse import fulltext
from .schemas import PaperReport


def prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def fingerprint(data) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


class EvidenceError(ValueError):
    def __init__(self, kind: str, anchor: str = ""):
        self.kind = kind
        super().__init__(f"Unverified evidence ({kind}) at anchor {anchor}")


def validate_evidence(report: PaperReport, sections: dict):
    for entry in report.paper_facts + report.methods + report.critical_gaps + report.testable_hypotheses:
        evidence = entry.evidence
        quote = " ".join(evidence.quote.split())
        text = " ".join(sections.get(evidence.anchor, "").split())
        if evidence.anchor not in sections:
            raise EvidenceError('unknown_anchor', evidence.anchor)
        if len(quote) < 16:
            raise EvidenceError('short_quote', evidence.anchor)
        if quote not in text:
            raise EvidenceError('quote_not_found', evidence.anchor)
    if not report.paper_facts:
        raise EvidenceError('no_facts')


def analyze(paper: Paper, team_id, requested_tier: str, fetch: Fetcher) -> Analysis | None:
    # Fulltext retrieval is itself cached, and only high-priority papers request it.
    doc = fulltext(paper, fetch) if requested_tier == "deep" and settings().llm_enabled else None
    tier = "deep" if doc else "medium"
    sections = doc.sections if doc else {"abstract": paper.abstract}
    source = {"kind": doc.kind if doc else "abstract", "truncated": doc.truncated if doc else False,
              "requested_tier": requested_tier, "sections": sections}
    model = settings().deep_model if tier == "deep" else settings().cheap_model
    instruction = prompt("analysis")
    prompt_hash = fingerprint(instruction)
    cache_key = fingerprint([paper.id, paper.arxiv_version, source["kind"], sections, tier,
                             settings().llm_cache_identity, model, prompt_hash])
    with session() as db:
        db.execute(text("SET LOCAL idle_in_transaction_session_timeout = 0"))
        lock(db, f"analysis:{cache_key}")
        cached = db.scalar(select(Analysis).where(Analysis.cache_key == cache_key))
        if cached:
            return cached
        try:
            report = llm.structured(team_id, model, "analysis", instruction,
                                    {"title": paper.title, "source": source}, PaperReport)
        except BudgetExceeded:
            if tier == "deep":
                # A full-text reservation may not fit while a shorter abstract analysis still does.
                return analyze(paper, team_id, "medium", fetch)
            return None
        except LLMDisabled:
            return None
        validate_evidence(report, sections)
        embedding = None
        try:
            embedding = llm.embed(team_id, [paper.title + "\n" + report.summary])[0]
        except Exception:
            # A search-index failure must not discard an already paid, evidence-checked report.
            pass
        analysis = Analysis(cache_key=cache_key, paper_id=paper.id, tier=tier, model=model,
                            prompt_version=prompt_hash, report={**report.model_dump(), "source": {
                                "kind": source["kind"], "truncated": source["truncated"],
                                "requested_tier": requested_tier, "evidence_checked": True,
                                "paper_version": paper.arxiv_version,
                                "paper_updated_at": str(paper.updated_at)}},
                            embedding=embedding, embedding_model=settings().embedding_model if embedding else None)
        db.add(analysis)
        db.flush()
        return analysis

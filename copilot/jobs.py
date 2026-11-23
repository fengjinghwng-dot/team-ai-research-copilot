import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text

from .analyze import analyze
from .budget import budget_day
from .config import settings
from .db import lock, session
from .deliver import push_email, push_group
from .fetch import Fetcher
from .ingest import collect
from .models import Analysis, Digest, JobRun, Paper, Team, TeamPaper, User, utcnow
from .rank import candidate_data, route, score_papers, team_context
from .weekly import build_reading, build_weekly

log = logging.getLogger(__name__)


def add_summaries(db, result):
    for item in result:
        analysis = db.scalar(select(Analysis).where(Analysis.paper_id == UUID(item["paper_id"]))
                             .order_by(Analysis.created_at.desc()).limit(1))
        item["analysis_state"] = "ready" if analysis else "metadata_only"
        if analysis:
            paper = db.get(Paper, UUID(item["paper_id"]))
            item["analysis_stale"] = analysis.report.get("source", {}).get("paper_version") != paper.arxiv_version
            item["summary"] = analysis.report["summary"]
            item["innovation"] = analysis.report["innovation"]
            item["analysis_tier"] = analysis.tier
        # Internal topic feature vectors are not needed in push payloads.
        item.pop("relevance", None)


def run_team(team_id, fetch, now):
    with session() as db:
        papers = db.scalars(select(Paper).join(TeamPaper, TeamPaper.paper_id == Paper.id).where(
            TeamPaper.team_id == team_id, Paper.first_date_verified.is_(True),
            Paper.first_submitted_at >= now - timedelta(hours=72), Paper.first_submitted_at <= now)
            .order_by(Paper.first_submitted_at.desc()).limit(200)).all()
    score_papers(team_id, papers)
    with session() as db:
        weights, _, members = team_context(db, team_id)
        candidates = candidate_data(db, team_id, papers)
        union = {}
        for member in members:
            for label, weight in member.interests.items():
                union[label] = max(union.get(label, 0), weight)
        selection = route(candidates, weights, union, settings().shortlist_size, settings().exploration_ratio)
    by_id = {str(p.id): p for p in papers}
    failures = []
    for i, item in enumerate(selection["items"]):
        try:
            analyze(by_id[item["paper_id"]], team_id,
                    "deep" if i < settings().deep_count else "medium", fetch)
        except Exception as exc:
            failures.append({"paper_id": item["paper_id"], "error": type(exc).__name__})
            log.warning("Analysis skipped paper=%s error=%s", item["paper_id"], type(exc).__name__)
    day, notifications = budget_day(), []
    with session() as db:
        # Group consensus uses team directions; private interests never appear in group cards.
        group_items = route(candidates, weights, {}, 5, settings().exploration_ratio)["items"]
        add_summaries(db, group_items)
        for member in members:
            personal = route(candidates, weights, member.interests, 20, settings().exploration_ratio)
            add_summaries(db, personal["items"])
            digest = {"team_must_read": group_items, "personal": personal,
                      "generated_at": now.isoformat(), "llm_enabled": settings().llm_enabled}
            db.merge(Digest(team_id=team_id, user_id=member.user_id, day=day, payload=digest))
            notifications.append((db.get(User, member.user_id), personal))
    push_group(team_id, day, group_items)
    for user, personal in notifications:
        push_email(user, team_id, day, personal)
    return {"candidates": len(papers), "selected": len(selection["items"]),
            "members": len(members), "analysis_failures": failures}


def run(kind: str = "daily", cache_only: bool = False, limit: int = 200):
    now = datetime.now(UTC)
    stats = {}
    # Session-independent work uses a dedicated lock-holding connection. No idle transaction timeout
    # dependency: keep this transaction alive with heartbeat before each team.
    with session() as guard:
        guard.execute(text("SET LOCAL idle_in_transaction_session_timeout = 0"))
        if not lock(guard, f"pipeline:{kind}", wait=False):
            return {"state": "already_running"}
        teams = guard.scalars(select(Team)).all()
        if not teams:
            return {"state": "no_teams", "message": "Bootstrap a team before scheduling the pipeline"}
        fetch = Fetcher(cache_only=cache_only or settings().use_cache_only)
        ingest_error = None
        if kind == "daily":
            try:
                stats["ingest"] = collect(fetch, [t.id for t in teams], now, limit=limit)
            except Exception as exc:
                ingest_error = type(exc).__name__
                stats["ingest"] = {"error": ingest_error}
                log.warning("Ingest failed; using existing verified candidates: %s", ingest_error)
        for team in teams:
            guard.execute(select(Team.id).limit(1))
            with session() as db:
                job = JobRun(kind=kind, team_id=team.id)
                db.add(job)
                db.flush()
                job_id = job.id
            try:
                if kind == "daily":
                    result = run_team(team.id, fetch, now)
                elif kind == "reading":
                    result = build_reading(team.id, budget_day())
                else:
                    result = build_weekly(team.id, budget_day())
                if ingest_error:
                    result["ingest_error"] = ingest_error
                state = "degraded" if ingest_error or result.get("analysis_failures") else "succeeded"
            except Exception as exc:
                result, state = {"error": type(exc).__name__}, "failed"
                log.exception("Team job failed team=%s", team.id)
            with session() as db:
                job = db.get(JobRun, job_id)
                job.state, job.stats, job.finished_at = state, result, utcnow()
            stats[str(team.id)] = {"state": state, **result}
    return stats

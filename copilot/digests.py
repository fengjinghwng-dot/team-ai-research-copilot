"""Team editions and member routing. Dashboard reads never call a model or send messages."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .models import Analysis, DailyEdition, Digest, Paper, TeamPaper, utcnow
from .rank import candidate_data, route, team_context


def add_summaries(db, result):
    for item in result:
        analysis = db.scalar(select(Analysis).where(Analysis.paper_id == UUID(item["paper_id"]))
                             .order_by(Analysis.created_at.desc()).limit(1))
        item["analysis_state"] = "ready" if analysis else "metadata_only"
        if analysis:
            paper = db.get(Paper, UUID(item["paper_id"]))
            item["analysis_stale"] = analysis.report.get("source", {}).get("paper_version") != paper.arxiv_version
            item["summary"], item["innovation"] = analysis.report["summary"], analysis.report["innovation"]
            item["analysis_tier"] = analysis.tier
        item.pop("relevance", None)


def edition_for_day(db, team_id, day):
    existing = db.get(DailyEdition, (team_id, day))
    if existing:
        return existing
    # Upgrade an old team snapshot without reading another member's private recommendations.
    legacy = db.execute(select(Digest.payload["team_must_read"],
        Digest.payload["generated_at"].as_string(), Digest.payload["llm_enabled"]).where(
        Digest.team_id == team_id, Digest.day == day).order_by(
        func.jsonb_array_length(Digest.payload["team_must_read"]).desc().nullslast()).limit(1)).first()
    if not legacy or not legacy[1]:
        return None
    try:
        generated = datetime.fromisoformat(legacy[1])
        generated = generated.replace(tzinfo=UTC) if generated.tzinfo is None else generated.astimezone(UTC)
    except (TypeError, ValueError):
        return None
    # Preserve the original edition's 72h window, even if a member joins later in the day.
    papers = db.scalars(select(Paper).join(TeamPaper, TeamPaper.paper_id == Paper.id).where(
        TeamPaper.team_id == team_id, Paper.first_date_verified.is_(True),
        Paper.first_submitted_at >= generated - timedelta(hours=72), Paper.first_submitted_at <= generated)
        .order_by(Paper.first_submitted_at.desc()).limit(200)).all()
    payload = {"team_must_read": legacy[0] or [], "candidate_paper_ids": [str(p.id) for p in papers],
               "generated_at": generated.isoformat(), "llm_enabled": bool(legacy[2])}
    db.execute(insert(DailyEdition).values(team_id=team_id, day=day, payload=payload).on_conflict_do_nothing())
    return db.get(DailyEdition, (team_id, day))


def member_digest(db, ctx, day):
    existing = db.get(Digest, (ctx.team_id, ctx.user.id, day))
    if existing and (existing.payload.get("team_must_read") or existing.payload.get("personal", {}).get("items")):
        payload = deepcopy(existing.payload)
        add_summaries(db, payload.get("team_must_read", []))
        add_summaries(db, payload.get("personal", {}).get("items", []))
        return payload
    edition = edition_for_day(db, ctx.team_id, day)
    if not edition:
        return existing.payload if existing else None
    papers = db.scalars(select(Paper).join(TeamPaper, TeamPaper.paper_id == Paper.id).where(
        TeamPaper.team_id == ctx.team_id, Paper.id.in_(
            [UUID(value) for value in edition.payload["candidate_paper_ids"]]))).all()
    weights, _, _ = team_context(db, ctx.team_id)
    personal = route(candidate_data(db, ctx.team_id, papers), weights, ctx.membership.interests,
                     20, settings().exploration_ratio)
    add_summaries(db, personal["items"])
    shared = deepcopy(edition.payload["team_must_read"])
    add_summaries(db, shared)
    payload = {"team_must_read": shared, "personal": personal,
               "generated_at": edition.payload["generated_at"], "personal_generated_at": utcnow().isoformat(),
               "llm_enabled": edition.payload["llm_enabled"],
               "message": "已复用该日团队日报生成你的推荐，未新增 AI 调用。"}
    statement = insert(Digest).values(team_id=ctx.team_id, user_id=ctx.user.id, day=day, payload=payload)
    db.execute(statement.on_conflict_do_update(index_elements=[Digest.team_id, Digest.user_id, Digest.day],
        set_={"payload": statement.excluded.payload}, where=(
            func.jsonb_array_length(Digest.payload["team_must_read"]) == 0) & (
            func.jsonb_array_length(Digest.payload["personal"]["items"]) == 0)))
    if existing:
        db.expire(existing)
    return db.get(Digest, (ctx.team_id, ctx.user.id, day)).payload

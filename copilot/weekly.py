from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select

from . import llm
from .analyze import prompt
from .budget import BudgetExceeded
from .config import settings
from .db import session
from .llm import LLMDisabled
from .models import Analysis, Claim, Paper, TeamPaper, Topic, User, Vote, WeeklyReport
from .schemas import TrendReport


def week_start(day):
    return day - timedelta(days=day.weekday())


def reading_markdown(db, team_id, day):
    start = week_start(day)
    end = start + timedelta(days=7)
    claims = db.scalars(select(Claim).where(Claim.team_id == team_id, Claim.meeting_date >= start,
                                          Claim.meeting_date < end)).all()
    start_dt = datetime.combine(start, time.min, ZoneInfo(settings().timezone))
    end_dt = datetime.combine(end, time.min, ZoneInfo(settings().timezone))
    votes = db.scalars(select(Vote).where(Vote.team_id == team_id, Vote.created_at >= start_dt,
                                         Vote.created_at < end_dt, Vote.value == 1)).all()
    ids = {c.paper_id for c in claims} | {v.paper_id for v in votes}
    lines = [f"# Weekly Reading List · {start} – {end - timedelta(days=1)}", ""]
    for paper_id in sorted(ids, key=str):
        paper = db.get(Paper, paper_id)
        title = paper.title.replace("[", "(").replace("]", ")")
        lines.extend([f"## [{title}]({paper.source_url})", ""])
        for claim in [c for c in claims if c.paper_id == paper_id]:
            user = db.get(User, claim.user_id)
            lines.append(f"- 分享人：{user.display_name or str(user.id)}；组会日期：{claim.meeting_date}")
        lines.append(f"- 本周赞数：{sum(v.paper_id == paper_id for v in votes)}")
        analysis = db.scalar(select(Analysis).where(Analysis.paper_id == paper_id)
                             .order_by(Analysis.created_at.desc()).limit(1))
        if analysis:
            lines.extend(["", analysis.report["summary"]])
        lines.append("")
    if not ids:
        lines.append("本周暂无高赞或认领论文。")
    return "\n".join(lines)


def cluster_vectors(items: list[Analysis], threshold: float = .78) -> list[list[Analysis]]:
    groups, centers = [], []
    for item in items:
        vector = np.asarray(item.embedding, dtype=float)
        norm = np.linalg.norm(vector)
        if not norm:
            continue
        vector /= norm
        distances = [float(np.dot(vector, center)) for center in centers]
        best = int(np.argmax(distances)) if distances else -1
        if best >= 0 and distances[best] >= threshold:
            groups[best].append(item)
            center = np.mean([np.asarray(a.embedding) for a in groups[best]], axis=0)
            centers[best] = center / max(np.linalg.norm(center), 1e-10)
        else:
            groups.append([item])
            centers.append(vector)
    return [group for group in groups if len(group) >= 2]


def group_by_topics(items, features, labels):
    """Explicit topic grouping for deployments without embeddings; never labelled semantic clustering."""
    buckets = {}
    for item in items:
        scores = features.get(item.paper_id, {})
        matches = [(scores.get(label, 0), label) for label in labels if scores.get(label, 0) >= .4]
        if matches:
            label = max(matches)[1]
            buckets.setdefault(label, []).append(item)
    return [group for _, group in sorted(buckets.items()) if len(group) >= 2]


def build_weekly(team_id, day):
    week = week_start(day)
    start = datetime.combine(week, time.min, ZoneInfo(settings().timezone))
    with session() as db:
        prior = db.get(WeeklyReport, (team_id, week))
        if prior and prior.payload.get("state") == "generated":
            return prior.payload
        # Latest report per paper, restricted to this team's high scoring arrivals this week.
        analyses = db.scalars(select(Analysis).join(TeamPaper, TeamPaper.paper_id == Analysis.paper_id).where(
            TeamPaper.team_id == team_id, TeamPaper.discovered_at >= start,
            TeamPaper.discovered_at < start + timedelta(days=7), TeamPaper.score >= .4)
            .order_by(Analysis.created_at.desc()).limit(300)).all()
        unique = {}
        for analysis in analyses:
            unique.setdefault(analysis.paper_id, analysis)
        latest = list(unique.values())
        groups = cluster_vectors([a for a in latest if a.embedding is not None and
                                 a.embedding_model == settings().embedding_model])
        grouping_method = "vector" if groups else "team_topics"
        if not groups:
            features = {p.paper_id: p.relevance for p in db.scalars(select(TeamPaper).where(
                TeamPaper.team_id == team_id, TeamPaper.paper_id.in_(unique)))}
            labels = db.scalars(select(Topic.label).where(Topic.team_id == team_id)).all()
            groups = group_by_topics(latest, features, labels)
        reading = reading_markdown(db, team_id, day)
    valid_ids, payload_groups = set(), []
    for group in groups[:8]:
        selected = group[:8]
        valid_ids.update(str(a.paper_id) for a in selected)
        payload_groups.append([{"paper_id": str(a.paper_id), "report": a.report} for a in selected])
    trends, state = [], "insufficient_evidence"
    if payload_groups:
        try:
            result = llm.structured(team_id, settings().deep_model, "weekly", prompt("trends"),
                                    {"grouping_method": grouping_method, "clusters": payload_groups}, TrendReport)
            for trend in result.trends:
                if len(set(trend.paper_ids)) < 2 or not set(trend.paper_ids) <= valid_ids:
                    raise ValueError("Weekly synthesis cited unknown or insufficient paper IDs")
            trends, state = result.model_dump()["trends"], "generated"
        except (BudgetExceeded, LLMDisabled):
            state = "budget_or_llm_disabled"
    payload = {"reading_list_markdown": reading, "trends": trends, "state": state,
               "hypotheses_verified": False, "grouping_method": grouping_method}
    with session() as db:
        db.merge(WeeklyReport(team_id=team_id, week=week, payload=payload))
    return payload


def build_reading(team_id, day):
    week = week_start(day)
    with session() as db:
        markdown = reading_markdown(db, team_id, day)
        prior = db.get(WeeklyReport, (team_id, week))
        payload = dict(prior.payload) if prior else {"trends": [], "state": "reading_list_only",
                                                    "hypotheses_verified": False}
        payload["reading_list_markdown"] = markdown
        db.merge(WeeklyReport(team_id=team_id, week=week, payload=payload))
    return payload

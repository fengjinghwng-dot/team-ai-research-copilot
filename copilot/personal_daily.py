"""Private daily preferences, deterministic selection and budgeted report generation."""
import math
import re
from datetime import timedelta

from sqlalchemy import and_, or_, select

from .analyze import analyze
from .config import settings
from .db import session
from .digests import add_summaries
from .models import DailyEdition, Digest, Membership, Paper, TeamPaper
from .personal_sources import CONFERENCE_YEARS, LATEST_HOURS, VENUES, discover_personal, keyword_variants
from .rank import candidate_data, route, team_context
from .schemas import DailyPreferences


def preferences_for(db, team_id, member):
    if member.daily_preferences:
        return DailyPreferences.model_validate(member.daily_preferences)
    weights, labels, _ = team_context(db, team_id)
    keywords = list(member.interests) or [word for label in weights for word in labels[label]]
    return DailyPreferences(keywords=(keywords or ["machine learning"])[:12])


def keyword_match(title, abstract, keywords):
    def normalize(value):
        return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())
    title, abstract = normalize(title), normalize(abstract)
    def contains(text, word):
        term = normalize(word)
        if term.isascii():
            return bool(re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", text))
        return term in text
    matches = [max(1.0 if contains(title, variant) else .8 if contains(abstract, variant) else 0
                   for variant in keyword_variants(word))
               for word in keywords if normalize(word)]
    return sum(matches) / max(1, len(matches))


def select_personal(candidates, preferences, weights, now):
    conference, latest = [], []
    since = now - timedelta(hours=LATEST_HOURS)
    for candidate in candidates:
        match = keyword_match(candidate["title"], candidate["abstract"], preferences.keywords)
        if match <= 0:
            continue
        candidate = {**candidate, "relevance": {**candidate["relevance"], "personal_keywords": match},
                     "reason": "匹配方向关键词：" + "、".join(preferences.keywords)}
        if (candidate.get("venue") in VENUES and candidate.get("venue_source") and
                now.year - CONFERENCE_YEARS + 1 <= (candidate.get("publication_year") or 0) <= now.year):
            candidate["selection_kind"] = "conference"
            conference.append(candidate)
        elif candidate.get("first_date_verified") and candidate.get("first_submitted_at"):
            from datetime import datetime
            submitted = datetime.fromisoformat(candidate["first_submitted_at"])
            if since <= submitted <= now:
                candidate["selection_kind"] = "latest"
                latest.append(candidate)
    count = preferences.paper_count
    target = math.floor(count * preferences.conference_ratio + .5)
    def ranked(pool):
        return route(pool, weights, {"personal_keywords": 1}, len(pool), settings().exploration_ratio)["items"]
    conference, latest = ranked(conference), ranked(latest)
    chosen = conference[:target] + latest[:count - target]
    chosen_ids = {item["paper_id"] for item in chosen}
    # Fill a source shortage with real eligible papers, retaining their actual source category.
    rest = sorted([item for item in conference + latest if item["paper_id"] not in chosen_ids],
                  key=lambda item: (-item["score"], item["paper_id"]))
    chosen.extend(rest[:max(0, count - len(chosen))])
    seen, unique = set(), []
    for item in chosen:
        if item["paper_id"] not in seen:
            seen.add(item["paper_id"])
            unique.append(item)
    actual = sum(item["selection_kind"] == "conference" for item in unique)
    warnings = []
    if len(unique) < count:
        warnings.append(f"符合方向和时间条件的论文不足：期望 {count} 篇，实际 {len(unique)} 篇")
    if actual != target:
        warnings.append(f"来源比例未达到目标：顶会目标 {target} 篇，实际 {actual} 篇，其余由可用来源补齐")
    return {"items": unique, "exploration_target": math.floor(len(unique) * settings().exploration_ratio + .5),
            "exploration_actual": sum(item["is_exploration"] for item in unique),
            "requested_count": count, "conference_target": target, "conference_actual": actual,
            "latest_actual": len(unique) - actual, "conference_ratio": preferences.conference_ratio,
            "keywords": preferences.keywords, "warnings": warnings}


def load_personal_pool(db, team_id, now):
    papers = db.scalars(select(Paper).join(TeamPaper, TeamPaper.paper_id == Paper.id).where(
        TeamPaper.team_id == team_id,
        or_(and_(Paper.first_date_verified.is_(True),
                 Paper.first_submitted_at >= now - timedelta(hours=LATEST_HOURS),
                 Paper.first_submitted_at <= now),
            and_(Paper.venue.in_(list(VENUES)), Paper.venue_source.is_not(None),
                 Paper.publication_year >= now.year - CONFERENCE_YEARS + 1,
                 Paper.publication_year <= now.year)))
        .order_by(Paper.first_submitted_at.desc().nullslast(), Paper.id).limit(1000)).all()
    candidates = candidate_data(db, team_id, papers)
    verified = {str(p.id): p.first_date_verified for p in papers}
    for item in candidates:
        item["first_date_verified"] = verified[item["paper_id"]]
    return papers, candidates


def generate_personal(team_id, user_id, preferences, fetch, now, day, *, kind="manual"):
    source_warnings, _ = discover_personal(fetch, team_id, preferences, now)
    with session() as db:
        if not db.get(Membership, (team_id, user_id)):
            raise ValueError("Membership no longer exists")
        weights, _, _ = team_context(db, team_id)
        papers, candidates = load_personal_pool(db, team_id, now)
        personal = select_personal(candidates, preferences, weights, now)
    by_id = {str(p.id): p for p in papers}
    stats = {"selected": len(personal["items"]), "reports_ready": 0, "reports_skipped": 0,
             "analysis_failures": [], "source_warnings": source_warnings}
    # Retrieval/routing are local. Only the selected papers enter paid neutral analysis.
    for index, item in enumerate(personal["items"]):
        if index >= settings().shortlist_size:
            stats["reports_skipped"] += 1
            continue
        try:
            report = analyze(by_id[item["paper_id"]], team_id,
                             "deep" if index < settings().deep_count else "medium", fetch)
            stats["reports_ready" if report else "reports_skipped"] += 1
        except Exception as exc:
            stats["analysis_failures"].append({"paper_id": item["paper_id"], "error": type(exc).__name__})
    with session() as db:
        member = db.scalar(select(Membership).where(Membership.team_id == team_id,
            Membership.user_id == user_id).with_for_update())
        if not member:
            raise ValueError("Membership no longer exists")
        add_summaries(db, personal["items"])
        edition = db.get(DailyEdition, (team_id, day))
        prior = db.get(Digest, (team_id, user_id, day))
        shared = edition.payload.get("team_must_read", []) if edition else (
            prior.payload.get("team_must_read", []) if prior else [])
        warnings = personal["warnings"] + source_warnings
        if settings().llm_enabled and (stats["reports_skipped"] or stats["analysis_failures"]):
            warnings.append("部分论文暂未生成新解读，已保留摘要或现有报告")
        personal["warnings"] = list(dict.fromkeys(warnings))
        payload = {"team_must_read": shared, "personal": personal,
                   "generated_at": now.isoformat(), "personal_generated_at": now.isoformat(),
                   "llm_enabled": settings().llm_enabled, "generation_kind": kind,
                   "message": "；".join(personal["warnings"]) or "已按你的方向与来源比例生成个人日报"}
        db.merge(Digest(team_id=team_id, user_id=user_id, day=day, payload=payload))
    stats.update(conference_actual=personal["conference_actual"], latest_actual=personal["latest_actual"],
                 warnings=personal["warnings"])
    return stats


def route_saved_pool(db, ctx, papers, now):
    preferences = preferences_for(db, ctx.team_id, ctx.membership)
    weights, _, _ = team_context(db, ctx.team_id)
    candidates = candidate_data(db, ctx.team_id, papers)
    verified = {str(p.id): p.first_date_verified for p in papers}
    for item in candidates:
        item["first_date_verified"] = verified[item["paper_id"]]
    return select_personal(candidates, preferences, weights, now)

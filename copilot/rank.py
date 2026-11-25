import math

from sqlalchemy import select

from . import llm
from .analyze import fingerprint, prompt
from .budget import BudgetExceeded
from .config import settings
from .db import session
from .llm import LLMDisabled
from .models import Claim, Membership, Paper, TeamPaper, Topic, Vote
from .schemas import RelevanceReport


def weighted_match(relevance: dict, weights: dict) -> float:
    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return sum(relevance.get(label, 0) * weight for label, weight in weights.items()) / total


def route(candidates: list[dict], team_weights: dict, interests: dict, count: int = 20,
          exploration_ratio: float = .2) -> dict:
    ranked = []
    for candidate in candidates:
        rel = candidate["relevance"]
        team = weighted_match(rel, team_weights)
        personal = weighted_match(rel, interests) if interests else team
        feedback = max(0, min(1, .5 + .15 * candidate.get("votes", 0) + .1 * candidate.get("claims", 0)))
        score = .5 * team + .3 * personal + .15 * feedback + .05 * candidate.get("quality", .5)
        ranked.append({**candidate, "score": round(score, 5), "team_match": round(team, 3),
                       "personal_match": round(personal, 3), "is_exploration": False})
    ranked.sort(key=lambda x: (-x["score"], x["paper_id"]))
    count = min(count, len(ranked))
    target = math.floor(count * exploration_ratio + .5)
    adjacent = [x for x in ranked if min(x["team_match"], x["personal_match"]) < .4
                and x.get("quality", 0) >= .55]
    adjacent.sort(key=lambda x: (-x.get("quality", 0), -x["score"], x["paper_id"]))
    explores = adjacent[:target]
    ids = {x["paper_id"] for x in explores}
    core = [x for x in ranked if x["paper_id"] not in ids][:count - len(explores)]
    return {"items": core + [{**x, "is_exploration": True} for x in explores],
            "exploration_target": target, "exploration_actual": len(explores)}


def team_context(db, team_id):
    topics = db.scalars(select(Topic).where(Topic.team_id == team_id)).all()
    members = db.scalars(select(Membership).where(Membership.team_id == team_id)).all()
    weights = {x.label: x.weight for x in topics}
    labels = {x.label: x.keywords for x in topics}
    for member in members:
        for label in member.interests:
            labels.setdefault(label, [label])
    return weights, labels, members


def score_papers(team_id, papers: list[Paper]):
    with session() as db:
        weights, labels, members = team_context(db, team_id)
    instruction = prompt("relevance")
    for paper in papers:
        cache_key = fingerprint([labels, instruction, settings().llm_cache_identity,
                                 settings().cheap_model, paper.abstract])
        with session() as db:
            link = db.get(TeamPaper, (team_id, paper.id))
            if not link:
                continue
            if link.relevance.get("_cache_key") == cache_key:
                continue
            try:
                report = llm.structured(team_id, settings().cheap_model, "ranking", instruction,
                                        {"topics": labels, "title": paper.title, "abstract": paper.abstract},
                                        RelevanceReport, max_output=1000)
                if set(x.label for x in report.topics) != set(labels) or len(report.topics) != len(labels):
                    raise ValueError("Relevance model changed or duplicated topic labels")
                rel = {x.label: x.score for x in report.topics}
                quality, reason = report.quality, report.reason
            except (BudgetExceeded, LLMDisabled):
                text = (paper.title + " " + paper.abstract).lower()
                rel = {label: float(any(word.lower() in text for word in words if word.strip()))
                       for label, words in labels.items()}
                quality, reason = .4, "仅关键词粗排；尚未进行 AI 相关性评估"
                # Do not mark fallback as a model cache hit: retry on a future budgeted run.
                cache_key = "keyword-fallback"
            except Exception:
                # Leave this paper available for metadata reading and future retry.
                continue
            link.relevance = {**rel, "_quality": quality, "_cache_key": cache_key}
            personal_union = {label: max((m.interests.get(label, 0) for m in members), default=0)
                              for label in labels}
            link.score = .6 * weighted_match(rel, weights) + .4 * weighted_match(rel, personal_union)
            # PostgreSQL cannot store NUL characters in model-generated explanations.
            link.reason = reason.replace("\x00", "")


def candidate_data(db, team_id, papers: list[Paper]) -> list[dict]:
    links = {x.paper_id: x for x in db.scalars(select(TeamPaper).where(TeamPaper.team_id == team_id))}
    votes, claims = {}, {}
    for vote in db.scalars(select(Vote).where(Vote.team_id == team_id)):
        votes[vote.paper_id] = votes.get(vote.paper_id, 0) + vote.value
    for claim in db.scalars(select(Claim).where(Claim.team_id == team_id)):
        claims[claim.paper_id] = claims.get(claim.paper_id, 0) + 1
    return [{"paper_id": str(p.id), "title": p.title, "abstract": p.abstract,
             "source_url": p.source_url, "arxiv_id": p.arxiv_id,
             "first_submitted_at": p.first_submitted_at.isoformat() if p.first_submitted_at else None,
             "venue": p.venue, "publication_year": p.publication_year, "venue_source": p.venue_source,
             "relevance": {k: v for k, v in links[p.id].relevance.items() if not k.startswith("_")},
             "quality": links[p.id].relevance.get("_quality", .4), "reason": links[p.id].reason,
             "votes": votes.get(p.id, 0), "claims": claims.get(p.id, 0)} for p in papers if p.id in links]

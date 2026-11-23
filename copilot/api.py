from datetime import date, timedelta
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from . import llm
from .auth import TeamContext, current_user, team_admin, team_member
from .budget import BudgetExceeded, budget_day
from .config import settings
from .db import get_db
from .llm import LLMDisabled
from .models import (
    Analysis,
    Annotation,
    BudgetUsage,
    Claim,
    Digest,
    Idea,
    JobRun,
    Membership,
    Paper,
    Team,
    TeamPaper,
    Topic,
    User,
    Vote,
    WeeklyReport,
    utcnow,
)
from .schemas import (
    AnnotationInput,
    ClaimInput,
    IdeaInput,
    IdeaPatch,
    MemberInput,
    ProfilePatch,
    TeamConfig,
    VoteInput,
)

app = FastAPI(title="Team AI Research Copilot", version="0.1.0",
              description="Team-scoped collaboration over a shared, evidence-checked paper analysis cache.")
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins,
                   allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"], allow_credentials=False)


def row(value, exclude=()):
    return jsonable_encoder({c.name: getattr(value, c.name) for c in value.__table__.columns
                             if c.name not in exclude})


def require_paper(db, ctx, paper_id):
    if not db.get(TeamPaper, (ctx.team_id, paper_id)):
        raise HTTPException(404, "Paper not found in this team")
    return db.get(Paper, paper_id)


@app.get("/healthz", tags=["system"])
def health():
    return {"status": "ok"}


@app.get("/readyz", tags=["system"])
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1 FROM copilot.teams LIMIT 1"))
    except Exception:
        raise HTTPException(503, "Database or migrations unavailable") from None
    return {"status": "ready", "llm_enabled": settings().llm_enabled,
            "sso_configured": bool(settings().supabase_url)}


@app.get("/v1/me", tags=["identity"])
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return {**row(user), "memberships": [row(m) for m in memberships]}


@app.get("/v1/teams/{team_id}/members", tags=["team"])
def members(ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    items = db.execute(select(User, Membership).join(Membership, Membership.user_id == User.id)
                       .where(Membership.team_id == ctx.team_id)).all()
    return {"items": [{"id": str(u.id), "display_name": u.display_name, "role": m.role} for u, m in items]}


@app.put("/v1/teams/{team_id}/members", tags=["team"])
def add_member(body: MemberInput, ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    # Serialize role changes so concurrent demotions cannot remove all administrators.
    db.scalar(select(Team).where(Team.id == ctx.team_id).with_for_update())
    if not db.get(User, body.user_id):
        raise HTTPException(404, "Member must log in and call /v1/me first")
    existing = db.get(Membership, (ctx.team_id, body.user_id))
    admins = db.scalar(select(func.count()).select_from(Membership).where(
        Membership.team_id == ctx.team_id, Membership.role == "admin"))
    if existing and existing.role == "admin" and body.role != "admin" and admins <= 1:
        raise HTTPException(409, "Cannot demote the last administrator")
    if existing:
        existing.role = body.role
    else:
        db.add(Membership(team_id=ctx.team_id, user_id=body.user_id, role=body.role))
    return {"ok": True}


@app.patch("/v1/teams/{team_id}/profile", tags=["team"])
def profile(body: ProfilePatch, ctx: TeamContext = Depends(team_member)):
    ctx.user.display_name = body.display_name
    ctx.user.email_opt_in = body.email_opt_in
    ctx.membership.interests = body.interests
    return {"ok": True}


@app.get("/v1/teams/{team_id}/config", tags=["team"])
def config(ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    team = db.get(Team, ctx.team_id)
    return {"team": row(team), "topics": [row(t) for t in db.scalars(
        select(Topic).where(Topic.team_id == ctx.team_id))], "interests": ctx.membership.interests,
        "role": ctx.membership.role, "exploration_ratio": settings().exploration_ratio}


@app.put("/v1/teams/{team_id}/config", tags=["team"])
def set_config(body: TeamConfig, ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    if len({t.label for t in body.topics}) != len(body.topics):
        raise HTTPException(422, "Topic labels must be unique")
    if body.daily_token_budget > settings().daily_token_limit:
        raise HTTPException(422, "Team limit cannot exceed deployment global limit")
    db.get(Team, ctx.team_id).daily_token_budget = body.daily_token_budget
    db.execute(delete(Topic).where(Topic.team_id == ctx.team_id))
    for topic in body.topics:
        db.add(Topic(team_id=ctx.team_id, **topic.model_dump()))
    return {"ok": True}


@app.get("/v1/teams/{team_id}/papers", tags=["papers"])
def papers(q: str = Query(default="", max_length=200), limit: int = Query(default=20, ge=1, le=100),
           offset: int = Query(default=0, ge=0, le=100000), ctx: TeamContext = Depends(team_member),
           db: Session = Depends(get_db)):
    query = select(Paper).join(TeamPaper, Paper.id == TeamPaper.paper_id).where(TeamPaper.team_id == ctx.team_id)
    if q:
        query = query.where(Paper.title.icontains(q, autoescape=True) | Paper.abstract.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Paper.first_submitted_at.desc(), Paper.id).limit(limit).offset(offset)).all()
    return {"items": [row(p) for p in items], "total": total, "limit": limit, "offset": offset}


@app.get("/v1/teams/{team_id}/daily", tags=["papers"])
def daily(day: date | None = None, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    day = day or budget_day()
    digest = db.get(Digest, (ctx.team_id, ctx.user.id, day))
    if digest:
        return {"day": str(day), **digest.payload, "persisted": True}
    # No external LLM request on dashboard reads. Empty states remain explicit.
    return {"day": str(day), "team_must_read": [], "personal": {"items": [], "exploration_target": 0,
            "exploration_actual": 0}, "persisted": False, "message": "日报尚未生成"}


@app.get("/v1/teams/{team_id}/papers/{paper_id}", tags=["papers"])
def detail(paper_id: UUID, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    paper = require_paper(db, ctx, paper_id)
    analyses = db.scalars(select(Analysis).where(Analysis.paper_id == paper_id)
                         .order_by(Analysis.created_at.desc()).limit(10)).all()
    return {"paper": row(paper), "analyses": [row(a, exclude=("embedding",)) for a in analyses],
            "annotations": [row(a) for a in db.scalars(select(Annotation).where(
                Annotation.team_id == ctx.team_id, Annotation.paper_id == paper_id).order_by(Annotation.created_at))],
            "claims": [row(c) for c in db.scalars(select(Claim).where(
                Claim.team_id == ctx.team_id, Claim.paper_id == paper_id))],
            "vote_total": db.scalar(select(func.coalesce(func.sum(Vote.value), 0)).where(
                Vote.team_id == ctx.team_id, Vote.paper_id == paper_id)),
            "my_vote": (db.get(Vote, (ctx.team_id, paper_id, ctx.user.id)).value
                        if db.get(Vote, (ctx.team_id, paper_id, ctx.user.id)) else 0)}


@app.post("/v1/teams/{team_id}/search", tags=["papers"])
def semantic_search(q: str = Query(min_length=2, max_length=500), limit: int = Query(default=20, ge=1, le=50),
                    ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    try:
        vector = llm.embed(ctx.team_id, [q])[0]
    except (BudgetExceeded, LLMDisabled):
        raise HTTPException(503, "Semantic search unavailable; use GET /papers?q= for keyword search") from None
    results = db.scalars(select(Analysis).join(TeamPaper, TeamPaper.paper_id == Analysis.paper_id).where(
        TeamPaper.team_id == ctx.team_id, Analysis.embedding.is_not(None),
        Analysis.embedding_model == settings().embedding_model)
        .order_by(Analysis.embedding.cosine_distance(vector)).limit(limit * 3)).all()
    seen, items = set(), []
    for analysis in results:
        if analysis.paper_id not in seen:
            seen.add(analysis.paper_id)
            items.append({"paper": row(db.get(Paper, analysis.paper_id)),
                          "analysis_id": str(analysis.id), "summary": analysis.report["summary"]})
    return {"items": items[:limit]}


@app.post("/v1/teams/{team_id}/papers/{paper_id}/annotations", tags=["collaboration"], status_code=201)
def annotate(paper_id: UUID, body: AnnotationInput, ctx: TeamContext = Depends(team_member),
             db: Session = Depends(get_db)):
    require_paper(db, ctx, paper_id)
    if body.parent_id:
        parent = db.get(Annotation, body.parent_id)
        if not parent or parent.team_id != ctx.team_id or parent.paper_id != paper_id:
            raise HTTPException(404, "Parent annotation not found on this team paper")
    item = Annotation(team_id=ctx.team_id, paper_id=paper_id, user_id=ctx.user.id, **body.model_dump())
    db.add(item)
    db.flush()
    return row(item)


@app.post("/v1/teams/{team_id}/papers/{paper_id}/claims", tags=["collaboration"], status_code=201)
def claim(paper_id: UUID, body: ClaimInput, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    require_paper(db, ctx, paper_id)
    if not budget_day() <= body.meeting_date <= budget_day() + timedelta(days=90):
        raise HTTPException(422, "Meeting date must be within the next 90 days")
    inserted = db.scalar(insert(Claim).values(team_id=ctx.team_id, paper_id=paper_id,
                         user_id=ctx.user.id, meeting_date=body.meeting_date)
                         .on_conflict_do_nothing().returning(Claim.id))
    existing = db.scalar(select(Claim).where(Claim.team_id == ctx.team_id, Claim.paper_id == paper_id,
                                           Claim.meeting_date == body.meeting_date))
    if not inserted and existing.user_id != ctx.user.id:
        raise HTTPException(409, "Paper already claimed for this meeting")
    return row(existing)


@app.delete("/v1/teams/{team_id}/claims/{claim_id}", tags=["collaboration"])
def unclaim(claim_id: UUID, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    item = db.get(Claim, claim_id)
    if not item or item.team_id != ctx.team_id:
        raise HTTPException(404, "Claim not found")
    if item.user_id != ctx.user.id and ctx.membership.role != "admin":
        raise HTTPException(403, "Only the claimant or administrator may release this claim")
    db.delete(item)
    return {"ok": True}


@app.put("/v1/teams/{team_id}/papers/{paper_id}/vote", tags=["collaboration"])
def vote(paper_id: UUID, body: VoteInput, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    require_paper(db, ctx, paper_id)
    db.execute(insert(Vote).values(team_id=ctx.team_id, paper_id=paper_id, user_id=ctx.user.id, value=body.value)
               .on_conflict_do_update(index_elements=["team_id", "paper_id", "user_id"],
                                      set_={"value": body.value, "created_at": utcnow()}))
    return {"ok": True}


@app.get("/v1/teams/{team_id}/ideas", tags=["ideas"])
def ideas(status: str | None = None, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    query = select(Idea).where(Idea.team_id == ctx.team_id)
    if status:
        query = query.where(Idea.status == status)
    return {"items": [row(i) for i in db.scalars(query.order_by(Idea.created_at.desc()).limit(200))]}


@app.post("/v1/teams/{team_id}/ideas", tags=["ideas"], status_code=201)
def add_idea(body: IdeaInput, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    require_paper(db, ctx, body.paper_id)
    if body.annotation_id:
        annotation = db.get(Annotation, body.annotation_id)
        if not annotation or annotation.team_id != ctx.team_id or annotation.paper_id != body.paper_id:
            raise HTTPException(404, "Source annotation not found on this team paper")
    idea = Idea(team_id=ctx.team_id, user_id=ctx.user.id, **body.model_dump())
    db.add(idea)
    db.flush()
    return row(idea)


@app.patch("/v1/teams/{team_id}/ideas/{idea_id}", tags=["ideas"])
def update_idea(idea_id: UUID, body: IdeaPatch, ctx: TeamContext = Depends(team_member),
                db: Session = Depends(get_db)):
    idea = db.get(Idea, idea_id)
    if not idea or idea.team_id != ctx.team_id:
        raise HTTPException(404, "Idea not found")
    if body.assignee_id and not db.get(Membership, (ctx.team_id, body.assignee_id)):
        raise HTTPException(422, "Assignee must belong to this team")
    idea.status, idea.assignee_id = body.status, body.assignee_id
    return row(idea)


@app.get("/v1/teams/{team_id}/reading-list", tags=["meetings"])
def reading_list(week: date | None = None, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    from .weekly import reading_markdown
    return Response(reading_markdown(db, ctx.team_id, week or budget_day()), media_type="text/markdown",
                    headers={"Content-Disposition": 'attachment; filename="reading-list.md"'})


@app.get("/v1/teams/{team_id}/weekly", tags=["meetings"])
def weekly(ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    items = db.scalars(select(WeeklyReport).where(WeeklyReport.team_id == ctx.team_id)
                       .order_by(WeeklyReport.week.desc()).limit(12)).all()
    return {"items": [row(w) for w in items]}


@app.get("/v1/teams/{team_id}/admin/usage", tags=["admin"])
def usage(ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    items = db.scalars(select(BudgetUsage).where(BudgetUsage.scope == str(ctx.team_id))
                       .order_by(BudgetUsage.day.desc()).limit(30)).all()
    return {"items": [row(i) for i in items], "team_limit": db.get(Team, ctx.team_id).daily_token_budget,
            "llm_enabled": settings().llm_enabled}


@app.get("/v1/teams/{team_id}/admin/jobs", tags=["admin"])
def jobs(ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    return {"items": [row(j) for j in db.scalars(select(JobRun).where(
        JobRun.team_id == ctx.team_id).order_by(JobRun.started_at.desc()).limit(30))]}

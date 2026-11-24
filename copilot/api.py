from datetime import date, timedelta
from typing import Literal
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
from .digests import member_digest
from .invitations import accept_pending, admin_count
from .llm import LLMDisabled
from .membership_requests import cancel_for_removed_member, resolve_for_member
from .models import (
    Analysis,
    Annotation,
    BudgetUsage,
    Claim,
    Idea,
    Invitation,
    JobRun,
    JoinRequest,
    LLMCall,
    Membership,
    Paper,
    PaperState,
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
    InviteInput,
    JoinRequestInput,
    JoinRequestReview,
    MemberInput,
    PaperStatePatch,
    ProfilePatch,
    TeamConfig,
    VoteInput,
)

app = FastAPI(title="Team AI Research Copilot", version="0.2.0",
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
        db.execute(text("SELECT 1 FROM copilot.daily_editions LIMIT 1"))
    except Exception:
        raise HTTPException(503, "Database or migrations unavailable") from None
    return {"status": "ready", "daily_editions_ready": True, "llm_enabled": settings().llm_enabled,
            "sso_configured": bool(settings().supabase_url)}


@app.get("/v1/me", tags=["identity"])
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    accept_pending(db, user)
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return {**row(user), "memberships": [row(m) for m in memberships]}


@app.get("/v1/teams/available", tags=["membership requests"])
def available_teams(user: User = Depends(current_user), db: Session = Depends(get_db)):
    joined = select(Membership.team_id).where(Membership.user_id == user.id)
    teams = db.scalars(select(Team).where(Team.join_requests_enabled.is_(True), Team.id.not_in(joined))
                      .order_by(Team.name, Team.id).limit(100)).all()
    return {"items": [{"id": team.id, "name": team.name} for team in teams]}


@app.get("/v1/join-requests", tags=["membership requests"])
def my_join_requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.execute(select(JoinRequest, Team.name).join(Team, Team.id == JoinRequest.team_id).where(
        JoinRequest.user_id == user.id).order_by(JoinRequest.created_at.desc()).limit(100)).all()
    return {"items": [{**row(item), "team_name": name} for item, name in items]}


@app.post("/v1/teams/{team_id}/join-requests", tags=["membership requests"], status_code=201)
def request_join(team_id: UUID, body: JoinRequestInput, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    team = db.scalar(select(Team).where(Team.id == team_id).with_for_update())
    if not team or not team.join_requests_enabled:
        raise HTTPException(404, "该团队暂未开放申请，请联系管理员邀请")
    if db.get(Membership, (team_id, user.id)):
        raise HTTPException(409, "你已经是这个团队的成员")
    pending = db.scalar(select(JoinRequest).where(JoinRequest.team_id == team_id,
        JoinRequest.user_id == user.id, JoinRequest.status == "pending"))
    if pending:
        return row(pending)
    item = JoinRequest(team_id=team_id, user_id=user.id, message=body.message.strip())
    db.add(item)
    db.flush()
    return row(item)


@app.delete("/v1/join-requests/{request_id}", tags=["membership requests"])
def cancel_join_request(request_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(JoinRequest).where(JoinRequest.id == request_id, JoinRequest.user_id == user.id))
    if not item:
        raise HTTPException(404, "申请不存在")
    db.scalar(select(Team).where(Team.id == item.team_id).with_for_update())
    item = db.scalar(select(JoinRequest).where(JoinRequest.id == request_id)
                     .with_for_update().execution_options(populate_existing=True))
    if item.status not in {"pending", "cancelled"}:
        raise HTTPException(409, "这份申请已处理，不能撤回")
    item.status, item.reviewed_at = "cancelled", utcnow()
    return row(item)


@app.get("/v1/teams/{team_id}/join-requests", tags=["membership requests"])
def team_join_requests(status: Literal["pending", "approved", "rejected", "cancelled"] | None = "pending",
                       ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    query = select(JoinRequest, User).join(User, User.id == JoinRequest.user_id).where(
        JoinRequest.team_id == ctx.team_id)
    if status:
        query = query.where(JoinRequest.status == status)
    items = db.execute(query.order_by(JoinRequest.created_at.desc()).limit(200)).all()
    count = db.scalar(select(func.count()).select_from(JoinRequest).where(
        JoinRequest.team_id == ctx.team_id, JoinRequest.status == "pending"))
    return {"items": [{**row(item), "applicant_email": applicant.email,
                       "applicant_name": applicant.display_name} for item, applicant in items], "pending_count": count}


@app.post("/v1/teams/{team_id}/join-requests/{request_id}/review", tags=["membership requests"])
def review_join_request(request_id: UUID, body: JoinRequestReview, ctx: TeamContext = Depends(team_admin),
                        db: Session = Depends(get_db)):
    db.scalar(select(Team).where(Team.id == ctx.team_id).with_for_update())
    item = db.scalar(select(JoinRequest).where(JoinRequest.id == request_id, JoinRequest.team_id == ctx.team_id)
                     .with_for_update().execution_options(populate_existing=True))
    if not item:
        raise HTTPException(404, "申请不存在")
    target = "approved" if body.decision == "approve" else "rejected"
    if item.status != "pending":
        if item.status == target:
            return row(item)  # A duplicate approval must not re-add a subsequently removed member.
        raise HTTPException(409, "申请已处理，请刷新列表")
    if target == "approved":
        db.execute(insert(Membership).values(team_id=ctx.team_id, user_id=item.user_id,
            role="member", interests={}).on_conflict_do_nothing())
    item.status, item.reviewed_at, item.reviewed_by = target, utcnow(), ctx.user.id
    db.flush()
    return row(item)


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
    db.flush()
    resolve_for_member(db, ctx.team_id, body.user_id, ctx.user.id)
    return {"ok": True}


@app.delete("/v1/teams/{team_id}/members/{user_id}", tags=["team"])
def remove_member(user_id: UUID, ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    db.scalar(select(Team).where(Team.id == ctx.team_id).with_for_update())
    member = db.get(Membership, (ctx.team_id, user_id))
    if not member:
        raise HTTPException(404, "Member not found")
    if member.role == "admin" and admin_count(db, ctx.team_id) <= 1:
        raise HTTPException(409, "Cannot remove the last administrator")
    email = db.get(User, user_id).email.strip().lower()
    invitation = db.scalar(select(Invitation).where(Invitation.team_id == ctx.team_id, Invitation.email == email))
    if invitation:
        invitation.revoked_at = utcnow()
    db.delete(member)
    cancel_for_removed_member(db, ctx.team_id, user_id, ctx.user.id)
    return {"ok": True}


def invitation_row(item):
    state = ("revoked" if item.revoked_at else "accepted" if item.accepted_at else
             "expired" if item.expires_at <= utcnow() else "pending")
    return {**row(item), "state": state}


@app.get("/v1/teams/{team_id}/invitations", tags=["team"])
def invitations(ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    items = db.scalars(select(Invitation).where(Invitation.team_id == ctx.team_id)
                       .order_by(Invitation.created_at.desc()).limit(100)).all()
    return {"items": [invitation_row(item) for item in items],
            "login_url": settings().workspace_url.rstrip("/") + "/login"}


@app.post("/v1/teams/{team_id}/invitations", tags=["team"], status_code=201)
def invite(body: InviteInput, ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    db.scalar(select(Team).where(Team.id == ctx.team_id).with_for_update())
    member = db.scalar(select(Membership).join(User, User.id == Membership.user_id).where(
        Membership.team_id == ctx.team_id, func.lower(User.email) == body.email))
    if member:
        raise HTTPException(409, "This email already belongs to a team member")
    now = utcnow()
    db.execute(insert(Invitation).values(team_id=ctx.team_id, email=body.email, invited_by=ctx.user.id,
        expires_at=now + timedelta(days=7), created_at=now).on_conflict_do_update(
        index_elements=["team_id", "email"], set_={"invited_by": ctx.user.id, "created_at": now,
            "expires_at": now + timedelta(days=7), "accepted_at": None, "accepted_by": None, "revoked_at": None}))
    item = db.scalar(select(Invitation).where(Invitation.team_id == ctx.team_id, Invitation.email == body.email))
    return {**invitation_row(item), "email_sent": False,
            "login_url": settings().workspace_url.rstrip("/") + "/login"}


@app.delete("/v1/teams/{team_id}/invitations/{invitation_id}", tags=["team"])
def revoke_invitation(invitation_id: UUID, ctx: TeamContext = Depends(team_admin),
                      db: Session = Depends(get_db)):
    db.scalar(select(Team).where(Team.id == ctx.team_id).with_for_update())
    item = db.scalar(select(Invitation).where(Invitation.id == invitation_id,
                                            Invitation.team_id == ctx.team_id).with_for_update())
    if not item:
        raise HTTPException(404, "Invitation not found")
    item.revoked_at = utcnow()
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
    if body.team_name is not None:
        db.get(Team, ctx.team_id).name = body.team_name
    db.get(Team, ctx.team_id).daily_token_budget = body.daily_token_budget
    if body.join_requests_enabled is not None:
        db.get(Team, ctx.team_id).join_requests_enabled = body.join_requests_enabled
    db.execute(delete(Topic).where(Topic.team_id == ctx.team_id))
    for topic in body.topics:
        db.add(Topic(team_id=ctx.team_id, **topic.model_dump()))
    return {"ok": True}


@app.get("/v1/teams/{team_id}/papers", tags=["papers"])
def papers(q: str = Query(default="", max_length=200), limit: int = Query(default=20, ge=1, le=100),
           offset: int = Query(default=0, ge=0, le=100000), saved_only: bool = False, unread_only: bool = False,
           ctx: TeamContext = Depends(team_member),
           db: Session = Depends(get_db)):
    query = select(Paper).join(TeamPaper, Paper.id == TeamPaper.paper_id).where(TeamPaper.team_id == ctx.team_id)
    if q:
        query = query.where(Paper.title.icontains(q, autoescape=True) | Paper.abstract.icontains(q, autoescape=True))
    mine = select(PaperState.paper_id).where(PaperState.team_id == ctx.team_id, PaperState.user_id == ctx.user.id)
    if saved_only:
        query = query.where(Paper.id.in_(mine.where(PaperState.saved.is_(True))))
    if unread_only:
        query = query.where(Paper.id.not_in(mine.where(PaperState.is_read.is_(True))))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Paper.first_submitted_at.desc(), Paper.id).limit(limit).offset(offset)).all()
    states = {state.paper_id: state for state in db.scalars(select(PaperState).where(
        PaperState.team_id == ctx.team_id, PaperState.user_id == ctx.user.id,
        PaperState.paper_id.in_([paper.id for paper in items])))}
    return {"items": [{**row(p), "personal_state": serialize_paper_state(states.get(p.id))} for p in items],
            "total": total, "limit": limit, "offset": offset}


def personal_state(db, ctx, paper_id):
    item = db.get(PaperState, (ctx.team_id, ctx.user.id, paper_id))
    return serialize_paper_state(item)


def serialize_paper_state(item):
    return ({"saved": item.saved, "is_read": item.is_read, "note": item.note,
             "updated_at": item.updated_at.isoformat()} if item else
            {"saved": False, "is_read": False, "note": "", "updated_at": None})


@app.patch("/v1/teams/{team_id}/papers/{paper_id}/state", tags=["personal"])
def set_paper_state(paper_id: UUID, body: PaperStatePatch, ctx: TeamContext = Depends(team_member),
                    db: Session = Depends(get_db)):
    require_paper(db, ctx, paper_id)
    fields = body.model_dump(exclude_unset=True)
    db.execute(insert(PaperState).values(team_id=ctx.team_id, user_id=ctx.user.id, paper_id=paper_id, **fields)
               .on_conflict_do_update(index_elements=["team_id", "user_id", "paper_id"],
                                      set_={**fields, "updated_at": utcnow()}))
    db.expire_all()
    return personal_state(db, ctx, paper_id)


@app.get("/v1/teams/{team_id}/daily", tags=["papers"])
def daily(day: date | None = None, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    day = day or budget_day()
    payload = member_digest(db, ctx, day)
    if payload is not None:
        return {"day": str(day), **payload, "persisted": True}
    # No external LLM request on dashboard reads. Empty states remain explicit.
    return {"day": str(day), "team_must_read": [], "personal": {"items": [], "exploration_target": 0,
            "exploration_actual": 0}, "persisted": False, "message": "日报尚未生成"}


@app.get("/v1/teams/{team_id}/papers/{paper_id}", tags=["papers"])
def detail(paper_id: UUID, ctx: TeamContext = Depends(team_member), db: Session = Depends(get_db)):
    paper = require_paper(db, ctx, paper_id)
    analyses = db.scalars(select(Analysis).where(Analysis.paper_id == paper_id)
                         .order_by(Analysis.created_at.desc()).limit(10)).all()
    return {"paper": row(paper), "personal_state": personal_state(db, ctx, paper_id),
            "analyses": [row(a, exclude=("embedding",)) for a in analyses],
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
    calls = db.execute(select(LLMCall.day,
        func.coalesce(func.sum(LLMCall.input_tokens), 0), func.coalesce(func.sum(LLMCall.output_tokens), 0),
        func.coalesce(func.sum(LLMCall.cost_cny_upper), 0), func.count(LLMCall.id),
        func.count(LLMCall.id).filter(LLMCall.cost_cny_upper.is_(None))).where(
        LLMCall.team_id == ctx.team_id).group_by(LLMCall.day).order_by(LLMCall.day.desc()).limit(30)).all()
    cfg = settings()
    global_usage = db.get(BudgetUsage, ("global", budget_day()))
    remaining = cfg.effective_daily_token_limit - (global_usage.used + global_usage.reserved if global_usage else 0)
    return {"items": [row(i) for i in items], "team_limit": db.get(Team, ctx.team_id).daily_token_budget,
            "llm_enabled": cfg.llm_enabled, "provider": cfg.llm_provider,
            "daily_budget_cny": str(cfg.daily_budget_cny) if cfg.llm_provider != "openai" else None,
            "global_token_limit": cfg.effective_daily_token_limit, "global_tokens_remaining": max(0, remaining),
            "cost_basis": ("deepseek_flash_peak_upper_bound" if cfg.llm_provider == "deepseek" else
                           "configured_rates_upper_bound" if cfg.monetary_guard_rate is not None else "unpriced"),
            "spending": [{"day": str(day), "input_tokens": input_count, "output_tokens": output_count,
                          "estimated_cny_upper": str(cost), "calls": count, "unpriced_calls": unknown}
                         for day, input_count, output_count, cost, count, unknown in calls]}


@app.get("/v1/teams/{team_id}/admin/integrations", tags=["admin"])
def integrations(ctx: TeamContext = Depends(team_admin)):
    cfg = settings()
    email = ('resend' if cfg.resend_api_key and cfg.email_from else 'smtp' if
             cfg.smtp_host and cfg.smtp_username and cfg.smtp_password and cfg.email_from else 'none')
    return {"analysis_enabled": cfg.llm_enabled, "analysis_provider": cfg.llm_provider,
            "analysis_key_configured": bool(cfg.llm_api_key if cfg.llm_provider == 'openai_compatible' else
                                            cfg.deepseek_api_key if cfg.llm_provider == 'deepseek' else cfg.openai_api_key),
            "semantic_search_available": cfg.llm_enabled and cfg.llm_provider == 'openai',
            "email_digest_provider": email,
            "group_delivery_provider": cfg.im_provider if cfg.im_webhook_url and cfg.im_team_id == str(ctx.team_id) else 'none',
            "workspace_url": cfg.workspace_url, "daily_budget_cny": str(cfg.daily_budget_cny),
            "weekly_topic_fallback": True}


@app.get("/v1/teams/{team_id}/admin/jobs", tags=["admin"])
def jobs(ctx: TeamContext = Depends(team_admin), db: Session = Depends(get_db)):
    return {"items": [row(j) for j in db.scalars(select(JobRun).where(
        JobRun.team_id == ctx.team_id).order_by(JobRun.started_at.desc()).limit(30))]}

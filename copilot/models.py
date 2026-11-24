import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(schema="copilot")


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    daily_token_budget: Mapped[int] = mapped_column(Integer, default=300_000)
    join_requests_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)  # Supabase auth subject
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100), default="")
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)


class Membership(Base):
    __tablename__ = "memberships"
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="member")
    interests: Mapped[dict] = mapped_column(JSONB, default=dict)


class Topic(Base):
    __tablename__ = "team_topics"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    invited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("copilot.users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("team_id", "email"),)


class JoinRequest(Base):
    __tablename__ = "join_requests"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("copilot.users.id"))
    __table_args__ = (Index("join_requests_pending_unique", "team_id", "user_id", unique=True,
                           postgresql_where=text("status = 'pending'")),)


class Paper(Base):
    __tablename__ = "papers"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    arxiv_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    arxiv_version: Mapped[str | None] = mapped_column(String(120))
    doi: Mapped[str | None] = mapped_column(String(300), unique=True)
    s2_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(Text)
    normalized_title: Mapped[str] = mapped_column(Text, index=True)
    abstract: Mapped[str] = mapped_column(Text, default="")
    authors: Mapped[list] = mapped_column(JSONB, default=list)
    categories: Mapped[list] = mapped_column(JSONB, default=list)
    first_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_date_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str] = mapped_column(Text)
    code_urls: Mapped[list] = mapped_column(JSONB, default=list)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TeamPaper(Base):
    __tablename__ = "team_papers"
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), primary_key=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.papers.id"), primary_key=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    relevance: Mapped[dict] = mapped_column(JSONB, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")


class PaperState(Base):
    __tablename__ = "paper_states"
    team_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"), primary_key=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (ForeignKeyConstraint(["team_id", "paper_id"],
                                          ["copilot.team_papers.team_id", "copilot.team_papers.paper_id"],
                                          ondelete="CASCADE"),)


class Document(Base):
    __tablename__ = "documents"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.papers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    sections: Mapped[dict] = mapped_column(JSONB)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)


class Analysis(Base):
    __tablename__ = "paper_analyses"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.papers.id"), index=True)
    tier: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(64))
    report: Mapped[dict] = mapped_column(JSONB)
    embedding: Mapped[list | None] = mapped_column(Vector(1536))
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("analyses_embedding_hnsw", "embedding", postgresql_using="hnsw",
                            postgresql_ops={"embedding": "vector_cosine_ops"}),)


class Annotation(Base):
    __tablename__ = "annotations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), index=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.papers.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("copilot.annotations.id"))
    anchor: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"))
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.papers.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"))
    meeting_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("team_id", "paper_id", "meeting_date"),)


class Vote(Base):
    __tablename__ = "votes"
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), primary_key=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.papers.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Idea(Base):
    __tablename__ = "ideas"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), index=True)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.papers.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"))
    annotation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("copilot.annotations.id"))
    title: Mapped[str] = mapped_column(String(200))
    hypothesis: Mapped[str] = mapped_column(Text)
    experiment: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="backlog")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("copilot.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Digest(Base):
    __tablename__ = "digests"
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.users.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"), primary_key=True)
    week: Mapped[date] = mapped_column(Date, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class FetchCache(Base):
    __tablename__ = "fetch_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    body: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BudgetUsage(Base):
    __tablename__ = "budget_usage"
    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    used: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0)


class LLMCall(Base):
    __tablename__ = "llm_calls"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("copilot.teams.id"))
    day: Mapped[date] = mapped_column(Date)
    model: Mapped[str] = mapped_column(String(120))
    purpose: Mapped[str] = mapped_column(String(30))
    reserved: Mapped[int] = mapped_column(Integer)
    actual: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cached_input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cost_cny_upper: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    state: Mapped[str] = mapped_column(String(20), default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Delivery(Base):
    __tablename__ = "deliveries"
    key: Mapped[str] = mapped_column(String(250), primary_key=True)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(30))
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("copilot.teams.id"))
    state: Mapped[str] = mapped_column(String(20), default="running")
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

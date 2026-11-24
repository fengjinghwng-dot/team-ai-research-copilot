from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Strict):
    anchor: str
    quote: str


class Fact(Strict):
    statement: str
    evidence: Evidence


class Gap(Strict):
    statement: str
    kind: Literal["paper_stated", "inference"]
    evidence: Evidence


class Hypothesis(Strict):
    statement: str
    rationale: str
    evidence: Evidence
    experiment: str
    metric: str
    falsification: str


class PaperReport(Strict):
    summary: str
    innovation: str
    methods: list[Fact]
    paper_facts: list[Fact]
    critical_gaps: list[Gap]
    testable_hypotheses: list[Hypothesis]
    reviewer_view: str


class TopicScore(Strict):
    label: str
    score: float = Field(ge=0, le=1)


class RelevanceReport(Strict):
    topics: list[TopicScore]
    quality: float = Field(ge=0, le=1)
    reason: str


class Trend(Strict):
    bottleneck: str
    paper_ids: list[str]
    hypothesis: str
    experiment: str
    metric: str
    falsification: str


class TrendReport(Strict):
    trends: list[Trend]


class ProfilePatch(Strict):
    display_name: str = Field(max_length=100)
    interests: dict[str, Annotated[float, Field(ge=0, le=1)]] = Field(max_length=30)
    email_opt_in: bool = False


class TopicInput(Strict):
    label: str = Field(min_length=1, max_length=100)
    keywords: list[str] = Field(max_length=30)
    weight: float = Field(gt=0, le=1)


class TeamConfig(Strict):
    team_name: str | None = Field(default=None, min_length=1, max_length=120)
    topics: list[TopicInput] = Field(min_length=1, max_length=20)
    daily_token_budget: int = Field(ge=1000, le=100_000_000)
    join_requests_enabled: bool | None = None

    @field_validator("team_name", mode="before")
    @classmethod
    def trim_team_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class AnnotationInput(Strict):
    body: str = Field(min_length=1, max_length=10000)
    parent_id: UUID | None = None
    anchor: str | None = Field(default=None, max_length=200)


class ClaimInput(Strict):
    meeting_date: date


class VoteInput(Strict):
    value: Literal[-1, 0, 1]


class IdeaInput(Strict):
    paper_id: UUID
    annotation_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    hypothesis: str = Field(min_length=1, max_length=10000)
    experiment: str = Field(min_length=1, max_length=10000)


class IdeaPatch(Strict):
    status: Literal["backlog", "evaluating", "planned", "experimenting", "archived"]
    assignee_id: UUID | None = None


class MemberInput(Strict):
    user_id: UUID
    role: Literal["member", "admin"] = "member"


class InviteInput(Strict):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class PaperStatePatch(Strict):
    saved: bool = False
    is_read: bool = False
    note: str = Field(default="", max_length=10000)


class JoinRequestInput(Strict):
    message: str = Field(default="", max_length=1000)


class JoinRequestReview(Strict):
    decision: Literal["approve", "reject"]

class DailyPreferences(Strict):
    keywords: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(min_length=1, max_length=12)
    paper_count: int = Field(default=20, ge=1, le=50)
    conference_ratio: float = Field(default=0.3, ge=0, le=1)

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value):
        if isinstance(value, list) and all(isinstance(word, str) for word in value):
            return list(dict.fromkeys(word.strip() for word in value if word.strip()))
        return value

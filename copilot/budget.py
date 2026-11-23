from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .db import session
from .models import BudgetUsage, LLMCall, Team


class BudgetExceeded(RuntimeError):
    pass


def budget_day():
    return datetime.now(ZoneInfo(settings().timezone)).date()


def reserve(team_id: UUID, model: str, purpose: str, upper_bound: int) -> UUID:
    """Reserve before network I/O. Concurrent workers cannot oversubscribe remaining tokens."""
    with session() as db:
        team = db.get(Team, team_id)
        if not team:
            raise ValueError("Unknown billing team")
        day = budget_day()
        scopes = sorted([(str(team_id), team.daily_token_budget),
                         ("global", settings().effective_daily_token_limit)])
        rows = []
        for scope, limit in scopes:
            db.execute(insert(BudgetUsage).values(scope=scope, day=day, used=0, reserved=0)
                       .on_conflict_do_nothing())
            row = db.scalar(select(BudgetUsage).where(BudgetUsage.scope == scope, BudgetUsage.day == day)
                            .with_for_update())
            if row.used + row.reserved + upper_bound > limit:
                raise BudgetExceeded(f"Daily token budget exhausted for {scope}")
            rows.append(row)
        for row in rows:
            row.reserved += upper_bound
        call = LLMCall(team_id=team_id, day=day, model=model, purpose=purpose, reserved=upper_bound)
        db.add(call)
        db.flush()
        return call.id


def settle(call_id: UUID, actual: int):
    with session() as db:
        call = db.scalar(select(LLMCall).where(LLMCall.id == call_id).with_for_update())
        if call.state == "settled":
            return
        for scope in sorted([str(call.team_id), "global"]):
            row = db.scalar(select(BudgetUsage).where(BudgetUsage.scope == scope, BudgetUsage.day == call.day)
                            .with_for_update())
            row.reserved -= call.reserved
            row.used += actual
        call.actual = actual
        call.state = "settled"


def uncertain(call_id: UUID):
    # Network failure may occur after the provider has charged. Keep the reservation for this day.
    with session() as db:
        call = db.get(LLMCall, call_id)
        call.state = "uncertain"

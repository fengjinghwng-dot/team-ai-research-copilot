"""Durable personal-daily queue, serialized across API replicas with a PostgreSQL lock."""
import logging
import threading
from contextlib import asynccontextmanager

from sqlalchemy import select, text

from .budget import budget_day
from .db import lock, session
from .fetch import Fetcher
from .models import Membership, PersonalDailyJob, utcnow
from .personal_daily import generate_personal
from .schemas import DailyPreferences

log = logging.getLogger(__name__)


def enqueue(db, ctx, preferences):
    # Serialize repeated clicks; the unique partial index is a second line of defence.
    member = db.scalar(select(Membership).where(Membership.team_id == ctx.team_id,
        Membership.user_id == ctx.user.id).with_for_update())
    if not member:
        raise ValueError("Membership no longer exists")
    active = db.scalar(select(PersonalDailyJob).where(PersonalDailyJob.team_id == ctx.team_id,
        PersonalDailyJob.user_id == ctx.user.id, PersonalDailyJob.state.in_(["queued", "running"])))
    if active:
        return active
    member.daily_preferences = preferences.model_dump()
    job = PersonalDailyJob(team_id=ctx.team_id, user_id=ctx.user.id, day=budget_day(),
                           preferences=preferences.model_dump())
    db.add(job)
    db.flush()
    return job


def process_next():
    # The lock lives on a dedicated connection while model calls use their normal budget transactions.
    # If a process stops, PostgreSQL releases it; another worker resumes the persisted job.
    with session() as guard:
        guard.execute(text("SET LOCAL idle_in_transaction_session_timeout = 0"))
        if not lock(guard, "personal-daily-worker", wait=False):
            return False
        with session() as db:
            job = db.scalar(select(PersonalDailyJob).where(
                PersonalDailyJob.state.in_(["queued", "running"]))
                .order_by(PersonalDailyJob.created_at, PersonalDailyJob.id).with_for_update(skip_locked=True).limit(1))
            if not job:
                return False
            job.state = "running"
            job_id, team_id, user_id = job.id, job.team_id, job.user_id
            preferences, now, day = DailyPreferences.model_validate(job.preferences), job.created_at, job.day
        try:
            stats = generate_personal(team_id, user_id, preferences, Fetcher(), now, day)
            state = "degraded" if stats.get("warnings") else "succeeded"
            error = None
        except Exception as exc:
            stats, state, error = {}, "failed", "生成失败，请稍后重试"
            log.warning("Personal daily failed job=%s error=%s", job_id, type(exc).__name__)
        with session() as db:
            job = db.get(PersonalDailyJob, job_id)
            if job:  # Removing a member cascades their queued jobs.
                job.state, job.stats, job.error, job.finished_at = state, stats, error, utcnow()
        return True


def worker_loop(stop):
    while not stop.is_set():
        try:
            worked = process_next()
        except Exception as exc:
            log.warning("Personal daily worker unavailable: %s", type(exc).__name__)
            worked = False
        if not worked:
            stop.wait(3)


@asynccontextmanager
async def lifespan(app):
    stop = threading.Event()
    thread = threading.Thread(target=worker_loop, args=(stop,), daemon=True, name="personal-daily")
    thread.start()
    try:
        yield
    finally:
        stop.set()

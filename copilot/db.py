import hashlib
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from .config import settings


@lru_cache
def engine():
    pool = create_engine(settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)
    @event.listens_for(pool, "connect")
    def configure_connection(connection, _):
        previous = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO copilot, extensions, public")
        finally:
            connection.autocommit = previous
    return pool


@contextmanager
def session():
    with Session(engine(), expire_on_commit=False) as db:
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise


def get_db():
    with session() as db:
        yield db


def lock(db: Session, key: str, wait: bool = True) -> bool:
    number = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    if wait:
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": number})
        return True
    return bool(db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": number}))

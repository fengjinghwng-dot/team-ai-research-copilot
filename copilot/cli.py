import hashlib
import json
import logging
from pathlib import Path
from uuid import UUID

import typer
from sqlalchemy import text

from .config import settings
from .db import engine, session
from .models import Membership, Team, Topic, User

app = typer.Typer(no_args_is_help=True)


def emit_job(result):
    typer.echo(json.dumps(result, ensure_ascii=False, default=str))
    failed = result.get("state") == "no_teams" or result.get("ingest", {}).get("error")
    failed = failed or any(isinstance(value, dict) and value.get("state") == "failed"
                           for value in result.values())
    if failed:
        raise typer.Exit(1)


@app.command()
def migrate():
    """Apply immutable, checksummed SQL migrations. Use a direct/session-mode Postgres connection."""
    with engine().begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(421579103)"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS copilot"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS copilot.schema_migrations "
                          "(name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz DEFAULT now())"))
        for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            previous = conn.scalar(text("SELECT checksum FROM copilot.schema_migrations WHERE name=:name"),
                                   {"name": path.name})
            if previous and previous != checksum:
                raise RuntimeError(f"Applied migration was modified: {path.name}")
            if previous:
                continue
            conn.connection.driver_connection.execute(sql, prepare=False)
            conn.execute(text("INSERT INTO copilot.schema_migrations(name,checksum) VALUES (:name,:checksum)"),
                         {"name": path.name, "checksum": checksum})
            typer.echo(f"Applied {path.name}")


@app.command()
def bootstrap(name: str, admin_id: UUID, admin_email: str):
    """Operator-only first team setup. admin_id must be an actual Supabase Auth user UUID."""
    with session() as db:
        user = db.get(User, admin_id)
        if not user:
            user = User(id=admin_id, email=admin_email, display_name="管理员")
            db.add(user)
            db.flush()
        team = Team(name=name)
        db.add(team)
        db.flush()
        db.add(Membership(team_id=team.id, user_id=admin_id, role="admin", interests={}))
        examples = [("LLM Agent", ["agent", "tool use"], .4),
                    ("RAG", ["retrieval", "retrieval-augmented"], .35),
                    ("Evaluation", ["evaluation", "benchmark"], .25)]
        for label, keywords, weight in examples:
            db.add(Topic(team_id=team.id, label=label, keywords=keywords, weight=weight))
        typer.echo(json.dumps({"team_id": str(team.id), "example_topics": True}))


@app.command()
def daily(use_cache: bool = False, limit: int = typer.Option(200, min=1, max=200)):
    """Run one shared pipeline, optionally replaying cached public sources only."""
    from .jobs import run
    logging.basicConfig(level=logging.INFO)
    emit_job(run("daily", use_cache, limit))


@app.command()
def check_provider():
    """Verify the custom provider key and model catalog with GET requests only."""
    from .provider_check import check_provider as check
    result = check()
    typer.echo(json.dumps(result))
    if not result["ok"]:
        raise typer.Exit(1)


@app.command()
def sample(count: int = typer.Option(3, min=1, max=5)):
    """Analyze a small real sample after configuring the key. No source ingest or delivery."""
    from .jobs import run_sample
    emit_job(run_sample(count))


@app.command()
def weekly():
    from .jobs import run
    emit_job(run("weekly"))


@app.command()
def reading():
    """Persist this week's reading list snapshot without LLM calls."""
    from .jobs import run
    emit_job(run("reading"))


@app.command()
def export_openapi(destination: Path = Path("contracts/openapi.json")):
    from .api import app as api
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(api.openapi(), indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8", newline="\n")
    typer.echo(str(destination))


@app.command()
def doctor():
    """Read-only readiness report. Never print secrets."""
    cfg = settings()
    result = {"llm_enabled": cfg.llm_enabled, "sso_configured": bool(cfg.supabase_url),
              "group_delivery_configured": bool(cfg.im_webhook_url and cfg.im_team_id),
              "email_configured": bool(cfg.email_from and (cfg.resend_api_key or
                                       (cfg.smtp_host and cfg.smtp_username and cfg.smtp_password)))}
    try:
        with session() as db:
            db.execute(text("SELECT 1 FROM copilot.teams LIMIT 1"))
        result["database_ready"] = True
    except Exception:
        result["database_ready"] = False
    typer.echo(json.dumps(result))


@app.command()
def prepare_eval(team_id: UUID, destination: Path = Path("evals/candidates.jsonl"),
                 limit: int = typer.Option(10, min=1, max=20),
                 fetch_count: int = typer.Option(3, min=0, max=10)):
    """Prepare actual public paper candidates and optional full-text caches. No LLM calls."""
    from .evaluation import prepare_candidates
    typer.echo(json.dumps(prepare_candidates(team_id, destination, limit, fetch_count)))


if __name__ == "__main__":
    app()

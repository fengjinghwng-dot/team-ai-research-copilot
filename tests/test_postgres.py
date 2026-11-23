"""Real PostgreSQL integration checks. CI supplies an isolated pgvector database."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from copilot.api import app
from copilot.auth import current_user
from copilot.db import get_db
from copilot.models import Base, BudgetUsage, Membership, Paper, Team, TeamPaper, User

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def pg_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; real PostgreSQL integration checks run in CI")
    engine = create_engine(url, pool_size=8)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS copilot"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client_data(pg_engine):
    # Random team IDs isolate tests without deleting any existing data.
    with Session(pg_engine, expire_on_commit=False) as db:
        user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.invalid")
        team, other = Team(name="A"), Team(name="B")
        db.add_all([user, team, other])
        db.flush()
        paper = Paper(title="Shared public paper", normalized_title=str(uuid.uuid4()),
                      source_url="https://arxiv.org/abs/2611.00001")
        secret_paper = Paper(title="Other team discovery", normalized_title=str(uuid.uuid4()),
                             source_url="https://arxiv.org/abs/2611.00002")
        db.add_all([paper, secret_paper])
        db.flush()
        db.add_all([Membership(team_id=team.id, user_id=user.id, role="member"),
                    TeamPaper(team_id=team.id, paper_id=paper.id),
                    TeamPaper(team_id=other.id, paper_id=secret_paper.id)])
        db.commit()
        ids = (team.id, other.id, paper.id, secret_paper.id)
    def scoped_db():
        with Session(pg_engine, expire_on_commit=False) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_db] = scoped_db
    app.dependency_overrides[current_user] = lambda: user
    yield TestClient(app), ids, user
    app.dependency_overrides.clear()


def test_team_isolation_and_admin_denial(client_data):
    client, (team, other, paper, hidden), _ = client_data
    assert client.get(f"/v1/teams/{other}/papers").status_code == 403
    assert client.get(f"/v1/teams/{team}/papers/{hidden}").status_code == 404
    assert client.get(f"/v1/teams/{team}/admin/usage").status_code == 403
    assert client.get(f"/v1/teams/{team}/papers").json()["total"] == 1


def test_idempotent_vote_and_claim(client_data):
    client, (team, _, paper, _), _ = client_data
    from copilot.budget import budget_day
    path = f"/v1/teams/{team}/papers/{paper}"
    for _ in range(2):
        assert client.put(path + "/vote", json={"value": 1}).status_code == 200
        assert client.post(path + "/claims", json={"meeting_date": budget_day().isoformat()}).status_code == 201
    detail = client.get(path).json()
    assert detail["vote_total"] == 1 and len(detail["claims"]) == 1


def test_discussion_and_idea_scope(client_data):
    client, (team, _, paper, hidden), _ = client_data
    path = f"/v1/teams/{team}"
    annotation = client.post(path + f"/papers/{paper}/annotations", json={"body": "Test comment"})
    assert annotation.status_code == 201
    denied = client.post(path + f"/papers/{hidden}/annotations", json={"body": "cross-team"})
    assert denied.status_code == 404
    idea = client.post(path + "/ideas", json={"paper_id": str(paper), "title": "Experiment",
                        "hypothesis": "Test measurable effect", "experiment": "Run controlled ablation",
                        "annotation_id": annotation.json()["id"]})
    assert idea.status_code == 201


def test_concurrent_budget_reservations_never_oversubscribe(pg_engine, monkeypatch):
    if os.environ.get("TEST_DB_EMBEDDED") == "true":
        pytest.skip("Concurrency requires independent Postgres backends; PGlite has a single WASM backend")
    from copilot import budget
    from copilot import db as db_module
    from copilot.db import session
    monkeypatch.setattr(db_module, "engine", lambda: pg_engine)
    with session() as db:
        team = Team(name="Budget concurrency", daily_token_budget=1000)
        db.add(team)
        db.flush()
        team_id = team.id
    def reserve_one(_):
        try:
            return budget.reserve(team_id, "test-model", "test", 600)
        except budget.BudgetExceeded:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve_one, range(2)))
    assert sum(x is not None for x in results) == 1
    with session() as db:
        usage = db.get(BudgetUsage, (str(team_id), budget.budget_day()))
        assert usage.reserved == 600 and usage.used == 0
    call_id = next(x for x in results if x)
    budget.settle(call_id, 400)
    with session() as db:
        usage = db.get(BudgetUsage, (str(team_id), budget.budget_day()))
        assert usage.reserved == 0 and usage.used == 400


def test_budget_reserve_settle_and_exhaustion(pg_engine, monkeypatch):
    from copilot import budget
    from copilot import db as db_module
    from copilot.db import session
    monkeypatch.setattr(db_module, "engine", lambda: pg_engine)
    with session() as db:
        team = Team(name="Budget accounting", daily_token_budget=1000)
        db.add(team)
        db.flush()
        team_id = team.id
    call = budget.reserve(team_id, "test-model", "test", 600)
    with pytest.raises(budget.BudgetExceeded):
        budget.reserve(team_id, "test-model", "test", 600)
    budget.settle(call, 200)
    budget.settle(call, 200)  # idempotent: settlement must not double-charge
    with session() as db:
        usage = db.get(BudgetUsage, (str(team_id), budget.budget_day()))
        assert usage.used == 200 and usage.reserved == 0
    unknown = budget.reserve(team_id, "test-model", "test", 600)
    budget.uncertain(unknown)
    with session() as db:
        usage = db.get(BudgetUsage, (str(team_id), budget.budget_day()))
        assert usage.used == 200 and usage.reserved == 600


def test_shared_analysis_cache_ignores_reader_identity(pg_engine, monkeypatch):
    from copilot import analyze as module
    from copilot import db as db_module
    from copilot.schemas import PaperReport
    monkeypatch.setattr(db_module, "engine", lambda: pg_engine)
    quote = "Our model uses retrieval to answer questions."
    with Session(pg_engine, expire_on_commit=False) as db:
        paper = Paper(title="Cache test", normalized_title=str(uuid.uuid4()), abstract=quote,
                      source_url="https://arxiv.org/abs/2611.12345")
        db.add(paper)
        db.commit()
    calls = []
    def paid_stub(*args, **kwargs):
        calls.append(args)
        return PaperReport(summary="Retrieval paper", innovation="Specific retrieval method", methods=[],
                           paper_facts=[{"statement": "Uses retrieval", "evidence": {
                               "anchor": "abstract", "quote": quote}}], critical_gaps=[],
                           testable_hypotheses=[], reviewer_view="Abstract-only assessment")
    monkeypatch.setattr(module.llm, "structured", paid_stub)
    monkeypatch.setattr(module.llm, "embed", lambda *args: [[.01] * 1536])
    first = module.analyze(paper, uuid.uuid4(), "medium", None)
    second = module.analyze(paper, uuid.uuid4(), "medium", None)
    assert first.id == second.id and len(calls) == 1


def test_dedup_versions_and_distinct_ids(pg_engine, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from copilot import db as db_module
    from copilot.ingest import upsert_paper
    monkeypatch.setattr(db_module, "engine", lambda: pg_engine)
    aid = "2611." + str(uuid.uuid4().int % 100000).zfill(5)
    title = "Dedup " + str(uuid.uuid4())
    first = datetime(2026, 11, 20, tzinfo=UTC)
    data = {"title": title, "arxiv_id": aid, "arxiv_version": aid + "v1", "abstract": "Test",
            "first_submitted_at": first, "updated_at": first, "first_date_verified": True,
            "source_url": f"https://arxiv.org/abs/{aid}"}
    one, created = upsert_paper(data.copy(), [])
    two, duplicate = upsert_paper({**data, "arxiv_version": aid + "v2",
                                  "updated_at": first + timedelta(days=1)}, [])
    assert created and not duplicate and one == two
    with Session(pg_engine) as db:
        paper = db.get(Paper, uuid.UUID(one))
        assert paper.first_submitted_at == first and paper.arxiv_version.endswith("v2")
    other_id = "2610." + aid.split(".")[1]
    third, created = upsert_paper({**data, "arxiv_id": other_id, "arxiv_version": other_id + "v1"}, [])
    assert created and third != one


def test_claim_conflict_and_owner_release(client_data, pg_engine):
    client, (team, _, paper, _), original = client_data
    from copilot.budget import budget_day
    path = f"/v1/teams/{team}"
    claimed = client.post(path + f"/papers/{paper}/claims", json={"meeting_date": str(budget_day())})
    with Session(pg_engine, expire_on_commit=False) as db:
        other = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.invalid")
        db.add(other)
        db.flush()
        db.add(Membership(team_id=team, user_id=other.id, role="member"))
        db.commit()
    app.dependency_overrides[current_user] = lambda: other
    conflict = client.post(path + f"/papers/{paper}/claims", json={"meeting_date": str(budget_day())})
    assert conflict.status_code == 409
    assert client.delete(path + f"/claims/{claimed.json()['id']}").status_code == 403
    app.dependency_overrides[current_user] = lambda: original

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


def test_money_ceiling_is_shared_across_teams(pg_engine, monkeypatch):
    from datetime import date, timedelta

    from copilot import budget
    from copilot import db as db_module
    from copilot.config import Settings
    from copilot.db import session
    cfg = Settings(_env_file=None, llm_provider="deepseek", cheap_model="deepseek-flash",
                   deep_model="deepseek-flash", daily_budget_cny="0.01", daily_token_limit=10000)
    day = date(2100, 1, 1) + timedelta(days=uuid.uuid4().int % 100000)
    monkeypatch.setattr(db_module, "engine", lambda: pg_engine)
    monkeypatch.setattr(budget, "settings", lambda: cfg)
    monkeypatch.setattr(budget, "budget_day", lambda: day)
    with session() as db:
        teams = [Team(name="Money cap A", daily_token_budget=10000),
                 Team(name="Money cap B", daily_token_budget=10000)]
        db.add_all(teams)
        db.flush()
        one, two = [team.id for team in teams]
    first = budget.reserve(one, "deepseek-flash", "test", 800)
    with pytest.raises(budget.BudgetExceeded):
        budget.reserve(two, "deepseek-flash", "test", 800)
    budget.uncertain(first)
    with pytest.raises(budget.BudgetExceeded):
        budget.reserve(two, "deepseek-flash", "test", 800)
    with session() as db:
        assert db.get(BudgetUsage, ("global", day)).reserved == 800
        assert db.get(BudgetUsage, (str(two), day)) is None  # failed reservation rolled back atomically


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


def test_email_invitation_binds_only_the_signed_in_email(client_data, pg_engine):
    client, (team, _, _, _), owner = client_data
    from copilot.models import Invitation
    path = f"/v1/teams/{team}/invitations"
    email = f"invite-{uuid.uuid4()}@test.invalid"
    assert client.post(path, json={"email": email}).status_code == 403
    with Session(pg_engine) as db:
        db.get(Membership, (team, owner.id)).role = "admin"
        db.commit()
    result = client.post(path, json={"email": ' ' + email.upper() + ' '})
    assert result.status_code == 201 and result.json()["email_sent"] is False
    assert result.json()["email"] == email
    assert client.post(path, json={"email": email, "role": "admin"}).status_code == 422
    with Session(pg_engine, expire_on_commit=False) as db:
        wrong = User(id=uuid.uuid4(), email=f"other-{uuid.uuid4()}@test.invalid")
        invited = User(id=uuid.uuid4(), email=email)
        db.add_all([wrong, invited])
        db.commit()
    app.dependency_overrides[current_user] = lambda: wrong
    assert client.get('/v1/me').json()["memberships"] == []
    app.dependency_overrides[current_user] = lambda: invited
    for _ in range(2):
        joined = client.get('/v1/me').json()["memberships"]
        assert len(joined) == 1 and joined[0]["role"] == "member"
    with Session(pg_engine) as db:
        invitation = db.get(Invitation, uuid.UUID(result.json()["id"]))
        assert invitation.accepted_by == invited.id
    app.dependency_overrides[current_user] = lambda: owner
    assert client.delete(f'/v1/teams/{team}/members/{owner.id}').status_code == 409
    assert client.delete(f'/v1/teams/{team}/members/{invited.id}').status_code == 200
    app.dependency_overrides[current_user] = lambda: invited
    assert client.get('/v1/me').json()["memberships"] == []  # Revoked invitations cannot re-add removed users.


def test_revoked_and_expired_invitations_cannot_grant_membership(client_data, pg_engine):
    from datetime import timedelta

    from copilot.models import Invitation, utcnow
    client, (team, _, _, _), owner = client_data
    with Session(pg_engine, expire_on_commit=False) as db:
        db.get(Membership, (team, owner.id)).role = "admin"
        target = User(id=uuid.uuid4(), email=f"expired-{uuid.uuid4()}@test.invalid")
        db.add(target)
        db.commit()
    path = f"/v1/teams/{team}/invitations"
    created = client.post(path, json={"email": target.email}).json()
    assert client.delete(path + '/' + created['id']).status_code == 200
    app.dependency_overrides[current_user] = lambda: target
    assert client.get('/v1/me').json()['memberships'] == []
    app.dependency_overrides[current_user] = lambda: owner
    assert client.post(path, json={"email": target.email}).status_code == 201
    with Session(pg_engine) as db:
        db.get(Invitation, uuid.UUID(created['id'])).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    app.dependency_overrides[current_user] = lambda: target
    assert client.get('/v1/me').json()['memberships'] == []


def test_personal_state_and_notes_are_private_to_account_and_team(client_data, pg_engine):
    client, (team, other, paper, hidden), owner = client_data
    path = f"/v1/teams/{team}"
    state_path = path + f"/papers/{paper}/state"
    assert client.patch(state_path, json={"saved": True, "note": "Private hypothesis"}).status_code == 200
    result = client.patch(state_path, json={"is_read": True}).json()
    assert result['saved'] and result['is_read'] and result['note'] == 'Private hypothesis'
    assert client.get(path + '/papers?saved_only=true').json()['total'] == 1
    assert client.get(path + '/papers?unread_only=true').json()['total'] == 0
    assert client.patch(path + f'/papers/{hidden}/state', json={"saved": True}).status_code == 404
    assert client.patch(f'/v1/teams/{other}/papers/{hidden}/state', json={"saved": True}).status_code == 403
    assert client.patch(state_path, json={"note": None}).status_code == 422
    with Session(pg_engine, expire_on_commit=False) as db:
        teammate = User(id=uuid.uuid4(), email=f"private-{uuid.uuid4()}@test.invalid")
        db.add(teammate)
        db.flush()
        db.add(Membership(team_id=team, user_id=teammate.id, role="member"))
        db.commit()
    app.dependency_overrides[current_user] = lambda: teammate
    detail = client.get(path + f'/papers/{paper}').json()
    assert detail['personal_state']['note'] == '' and not detail['personal_state']['saved']
    assert client.get(path + '/papers?saved_only=true').json()['total'] == 0
    assert client.get(path + '/papers?unread_only=true').json()['total'] == 1


def test_cost_usage_is_settled_once_and_is_team_scoped(client_data, pg_engine, monkeypatch):
    from decimal import Decimal

    from copilot import budget
    from copilot import db as db_module
    from copilot.models import LLMCall
    client, (team, _, _, _), owner = client_data
    monkeypatch.setattr(db_module, "engine", lambda: pg_engine)
    call = budget.reserve(team, 'deepseek-flash', 'test', 800)
    budget.settle(call, 150, input_tokens=100, output_tokens=50, cached_input_tokens=20)
    budget.settle(call, 150, input_tokens=100, output_tokens=50, cached_input_tokens=20)
    with Session(pg_engine) as db:
        item = db.get(LLMCall, call)
        assert item.cost_cny_upper == Decimal('0.00056080')
        assert item.input_tokens == 100 and item.output_tokens == 50
        db.get(Membership, (team, owner.id)).role = 'admin'
        db.commit()
    result = client.get(f'/v1/teams/{team}/admin/usage').json()
    assert result['spending'][0]['calls'] == 1
    assert result['spending'][0]['unpriced_calls'] == 0
    assert Decimal(result['spending'][0]['estimated_cny_upper']) == Decimal('0.00056080')


@pytest.mark.parametrize('fail', [False, True])
def test_smtp_delivery_escapes_html_and_never_retries_ambiguous_send(client_data, pg_engine, monkeypatch, fail):
    from datetime import date

    from copilot import db as db_module
    from copilot import deliver
    from copilot.config import Settings
    from copilot.models import Delivery
    _, (team, _, paper, _), user = client_data
    monkeypatch.setattr(db_module, 'engine', lambda: pg_engine)
    cfg = Settings(_env_file=None, smtp_host='smtp.test.invalid', smtp_username='placeholder',
                   smtp_password='placeholder', email_from='system@test.invalid')
    monkeypatch.setattr(deliver, 'settings', lambda: cfg)
    user.email_opt_in = True
    messages = []
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def login(self, *args):
            pass
        def send_message(self, message):
            messages.append(message)
            if fail:
                raise TimeoutError('ambiguous')
    monkeypatch.setattr(deliver.smtplib, 'SMTP_SSL', lambda *args, **kwargs: Connection())
    personal = {'items': [{'paper_id': str(paper), 'title': '<script>alert(1)</script>', 'reason': 'test'}]}
    for _ in range(2):
        deliver.push_email(user, team, date(2026, 11, 24), personal)
    assert len(messages) == 1
    body = messages[0].get_body(preferencelist=('html',)).get_content()
    assert '&lt;script&gt;' in body and '<script>' not in body
    with Session(pg_engine) as db:
        record = db.get(Delivery, f'email:{team}:{user.id}:2026-11-24')
        assert record.state == ('uncertain' if fail else 'sent')


def test_weekly_reading_list_tracks_current_votes_and_claims(client_data):
    from copilot.budget import budget_day
    client, (team, _, paper, _), _ = client_data
    path = f'/v1/teams/{team}'
    client.put(path + f'/papers/{paper}/vote', json={'value': 1})
    claim = client.post(path + f'/papers/{paper}/claims', json={'meeting_date': str(budget_day())}).json()
    reading = client.get(path + '/reading-list')
    assert reading.status_code == 200 and 'Shared public paper' in reading.text and '本周赞数：1' in reading.text
    client.delete(path + '/claims/' + claim['id'])
    client.put(path + f'/papers/{paper}/vote', json={'value': 0})
    assert '暂无高赞或认领论文' in client.get(path + '/reading-list').text


def application_users(pg_engine, team, owner):
    with Session(pg_engine, expire_on_commit=False) as db:
        db.get(Membership, (team, owner.id)).role = 'admin'
        db.get(Team, team).join_requests_enabled = True
        applicant = User(id=uuid.uuid4(), email=f'apply-{uuid.uuid4()}@test.invalid')
        outsider = User(id=uuid.uuid4(), email=f'outsider-{uuid.uuid4()}@test.invalid')
        db.add_all([applicant, outsider])
        db.commit()
    return applicant, outsider


def test_application_approval_requires_team_admin_and_cannot_be_replayed_after_removal(client_data, pg_engine):
    client, (team, other, _, _), owner = client_data
    applicant, outsider = application_users(pg_engine, team, owner)
    path = f'/v1/teams/{team}'
    app.dependency_overrides[current_user] = lambda: applicant
    available = client.get('/v1/teams/available').json()['items']
    assert any(item['id'] == str(team) for item in available)
    assert all(item['id'] != str(other) for item in available)
    assert all(set(item) == {'id', 'name'} for item in available)
    assert client.post(path + '/join-requests', json={'message': 'Research interests', 'role': 'admin'}).status_code == 422
    request = client.post(path + '/join-requests', json={'message': 'Research interests'}).json()
    assert client.post(path + '/join-requests', json={}).json()['id'] == request['id']
    assert client.get(path + '/papers').status_code == 403
    assert client.get(path + '/join-requests').status_code == 403
    app.dependency_overrides[current_user] = lambda: outsider
    assert client.get('/v1/join-requests').json()['items'] == []
    assert client.delete('/v1/join-requests/' + request['id']).status_code == 404
    assert client.post(path + '/join-requests/' + request['id'] + '/review', json={'decision': 'approve'}).status_code == 403
    app.dependency_overrides[current_user] = lambda: owner
    pending = client.get(path + '/join-requests').json()
    assert pending['pending_count'] == 1 and pending['items'][0]['applicant_email'] == applicant.email
    review = path + '/join-requests/' + request['id'] + '/review'
    assert client.post(f'/v1/teams/{other}/join-requests/{request["id"]}/review', json={'decision': 'approve'}).status_code == 403
    for _ in range(2):
        assert client.post(review, json={'decision': 'approve'}).json()['status'] == 'approved'
    app.dependency_overrides[current_user] = lambda: applicant
    assert client.get(path + '/papers').status_code == 200
    assert client.get('/v1/me').json()['memberships'][0]['role'] == 'member'
    app.dependency_overrides[current_user] = lambda: owner
    assert client.delete(path + '/members/' + str(applicant.id)).status_code == 200
    assert client.post(review, json={'decision': 'approve'}).status_code == 200
    app.dependency_overrides[current_user] = lambda: applicant
    assert client.get(path + '/papers').status_code == 403
    assert client.post(path + '/join-requests', json={}).json()['id'] != request['id']


def test_rejected_withdrawn_and_closed_applications_cannot_grant_access(client_data, pg_engine):
    client, (team, _, _, _), owner = client_data
    applicant, _ = application_users(pg_engine, team, owner)
    path = f'/v1/teams/{team}'
    app.dependency_overrides[current_user] = lambda: applicant
    first = client.post(path + '/join-requests', json={}).json()
    app.dependency_overrides[current_user] = lambda: owner
    assert client.post(path + '/join-requests/' + first['id'] + '/review', json={'decision': 'reject'}).json()['status'] == 'rejected'
    assert client.post(path + '/join-requests/' + first['id'] + '/review', json={'decision': 'approve'}).status_code == 409
    app.dependency_overrides[current_user] = lambda: applicant
    second = client.post(path + '/join-requests', json={}).json()
    assert second['id'] != first['id']
    assert client.delete('/v1/join-requests/' + second['id']).json()['status'] == 'cancelled'
    app.dependency_overrides[current_user] = lambda: owner
    assert client.post(path + '/join-requests/' + second['id'] + '/review', json={'decision': 'approve'}).status_code == 409
    old_config = {'topics': [{'label': 'RAG', 'keywords': ['retrieval'], 'weight': 1}], 'daily_token_budget': 10000}
    assert client.put(path + '/config', json=old_config).status_code == 200
    assert client.get(path + '/config').json()['team']['join_requests_enabled'] is True
    assert client.put(path + '/config', json={**old_config, 'join_requests_enabled': False}).status_code == 200
    app.dependency_overrides[current_user] = lambda: applicant
    assert client.post(path + '/join-requests', json={}).status_code == 404
    assert all(item['id'] != str(team) for item in client.get('/v1/teams/available').json()['items'])
    assert client.get(path + '/papers').status_code == 403


def test_an_accepted_email_invitation_resolves_a_pending_join_request(client_data, pg_engine):
    client, (team, _, _, _), owner = client_data
    applicant, _ = application_users(pg_engine, team, owner)
    path = f'/v1/teams/{team}'
    app.dependency_overrides[current_user] = lambda: applicant
    client.post(path + '/join-requests', json={'message': 'Please review'})
    app.dependency_overrides[current_user] = lambda: owner
    assert client.post(path + '/invitations', json={'email': applicant.email}).status_code == 201
    app.dependency_overrides[current_user] = lambda: applicant
    assert client.get('/v1/me').json()['memberships'][0]['role'] == 'member'
    assert client.get('/v1/join-requests').json()['items'][0]['status'] == 'approved'
    app.dependency_overrides[current_user] = lambda: owner
    assert client.get(path + '/join-requests').json()['pending_count'] == 0

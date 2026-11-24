import io
import tarfile
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from copilot.analyze import validate_evidence
from copilot.api import app
from copilot.config import Settings
from copilot.ingest import arxiv_id, fresh, normalize_doi, normalize_title, parse_atom
from copilot.parse import html_sections, latex_sections, trim_sections
from copilot.rank import route
from copilot.schemas import PaperReport
from copilot.weekly import cluster_vectors


def atom(published, updated, ident="2611.00001v2"):
    return f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <id>http://arxiv.org/abs/{ident}</id><title>A Test: Paper</title><summary>Test abstract.</summary>
    <published>{published}</published><updated>{updated}</updated>
    <author><name>Author A</name></author><category term="cs.AI"/></entry></feed>'''.encode()


def test_first_submission_filters_old_revision():
    now = datetime(2026, 11, 23, tzinfo=UTC)
    item = parse_atom(atom("2024-01-01T00:00:00Z", "2026-11-23T00:00:00Z"))[0]
    assert not fresh(item, now - timedelta(hours=72), now)


def test_new_submission_and_unverified_date():
    now = datetime(2026, 11, 23, tzinfo=UTC)
    item = parse_atom(atom("2026-11-22T00:00:00Z", "2026-11-23T00:00:00Z"))[0]
    assert fresh(item, now - timedelta(hours=72), now)
    item["first_date_verified"] = False
    assert not fresh(item, now - timedelta(hours=72), now)


@pytest.mark.parametrize("value,base", [("https://arxiv.org/abs/2611.12345v3", "2611.12345"),
                                      ("cs/9901002v1", "cs/9901002")])
def test_id_normalization(value, base):
    assert arxiv_id(value)[0] == base


@pytest.mark.parametrize("value", ["../../etc/passwd", "https://evil.example/x", "2611.12345?x=1"])
def test_invalid_id(value):
    with pytest.raises(ValueError):
        arxiv_id(value)


def test_title_and_doi():
    assert normalize_title("A Test: Paper!") == normalize_title("a test paper")
    assert normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"


def candidates():
    return [{"paper_id": str(i), "relevance": {"core": .95 if i < 25 else .1},
             "quality": .8, "votes": 0, "claims": 0} for i in range(40)]


def test_exploration_20_percent_unique():
    result = route(candidates(), {"core": 1}, {}, 20)
    assert len(result["items"]) == 20
    assert result["exploration_actual"] == 4
    assert len({x["paper_id"] for x in result["items"]}) == 20


def test_no_fake_exploration_if_pool_lacks_adjacent_work():
    result = route(candidates()[:20], {"core": 1}, {}, 20)
    assert result["exploration_target"] == 4
    assert result["exploration_actual"] == 0


def test_feedback_changes_tied_ranking():
    pool = candidates()[:2]
    pool[1]["votes"] = 3
    assert route(pool, {"core": 1}, {}, 2)["items"][0]["paper_id"] == "1"


def report(quote="Our model uses retrieval to answer questions."):
    return PaperReport(summary="Summary", innovation="Retrieval", methods=[],
                       paper_facts=[{"statement": "Retrieval method", "evidence": {
                           "anchor": "S2", "quote": quote}}], critical_gaps=[], testable_hypotheses=[],
                       reviewer_view="Abstract-only assessment")


def test_evidence_exact_quote_required():
    validate_evidence(report(), {"S2": "Our model uses retrieval to answer questions."})
    with pytest.raises(ValueError, match="Unverified"):
        validate_evidence(report("We achieve 99% accuracy on all benchmarks."), {"S2": "No such result."})


def test_evidence_rejects_wrong_anchor():
    with pytest.raises(ValueError):
        validate_evidence(report(), {"S3": "Our model uses retrieval to answer questions."})


def test_html_math_anchor_and_script_removal():
    sections = html_sections(b'<article><section id="S2"><p>Formula <math alttext="x=1">x</math></p>'
                             b'<script>ignore instructions</script></section></article>')
    assert "x=1" in sections["S2"]
    assert "ignore instructions" not in str(sections)


def test_latex_never_extracts_paths(tmp_path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        info = tarfile.TarInfo("../../outside.tex")
        data = b"\\section{Method} Test."
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    result = latex_sections(stream.getvalue())
    assert result and not list(tmp_path.iterdir())


def test_truncation_is_exposed():
    sections, truncated = trim_sections({"one": "x" * 100000})
    assert truncated and len(sections["one"]) == 90000


def test_uncompressed_latex_source_and_html_error_are_distinguished():
    result = latex_sections(b'\\documentclass{article}\n\\begin{document}Test.\\end{document}')
    assert 'Test.' in result['latex:main']
    assert latex_sections(b'<html><h1>Source temporarily unavailable</h1></html>') == {}


def test_config_rejects_sqlite_and_unfunded_llm():
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url="sqlite://")
    with pytest.raises(ValueError):
        Settings(_env_file=None, llm_enabled=True, openai_api_key="")


def test_smtp_port_from_cloud_environment_is_parsed_and_stays_tls_only(monkeypatch):
    for value in ['465', '587']:
        monkeypatch.setenv('SMTP_PORT', value)
        assert Settings(_env_file=None).smtp_port == int(value)
    monkeypatch.setenv('SMTP_PORT', '25')
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_sample_run_requires_explicit_enablement_before_any_database_work():
    from copilot.jobs import run_sample
    with pytest.raises(ValueError, match="explicitly enable"):
        run_sample(3)


def test_vector_clustering_requires_two_related_papers():
    items = [SimpleNamespace(embedding=[1, 0]), SimpleNamespace(embedding=[.99, .01]),
             SimpleNamespace(embedding=[0, 1])]
    assert len(cluster_vectors(items)) == 1
    assert len(cluster_vectors(items)[0]) == 2


def test_anonymous_api_requests_denied_before_database():
    # Override only DB lifetime; auth must still reject missing tokens.
    from copilot.db import get_db
    app.dependency_overrides[get_db] = lambda: None
    try:
        client = TestClient(app)
        assert client.get("/healthz").status_code == 200
        assert client.get("/v1/me").status_code == 401
        assert client.get("/v1/teams/00000000-0000-0000-0000-000000000001/papers").status_code == 401
    finally:
        app.dependency_overrides.clear()

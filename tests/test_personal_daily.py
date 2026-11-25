from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from copilot.personal_daily import keyword_match, select_personal
from copilot.personal_sources import (
    conference_name,
    conference_record,
    discover_personal,
    openalex_conference_record,
)
from copilot.schemas import DailyPreferences

NOW = datetime(2026, 11, 24, 4, tzinfo=UTC)


def candidate(number, *, conference=False, age=1, title="RAG retrieval", verified=True, venue_source=True):
    return {"paper_id": str(number), "title": title, "abstract": "Retrieval augmented generation.",
            "relevance": {}, "quality": .8, "votes": 0, "claims": 0,
            "first_submitted_at": (NOW - timedelta(hours=age)).isoformat(),
            "first_date_verified": verified, "venue": "ICML" if conference else None,
            "publication_year": 2025 if conference else None,
            "venue_source": "https://www.semanticscholar.org/paper/source" if conference and venue_source else None}


@pytest.mark.parametrize("ratio,expected", [(0, 0), (.25, 2), (.5, 4), (1, 8)])
def test_personal_count_and_source_ratio(ratio, expected):
    pool = [candidate(i, conference=True, age=1000) for i in range(10)]
    pool += [candidate(i + 10) for i in range(10)]
    preferences = DailyPreferences(keywords=["RAG"], paper_count=8, conference_ratio=ratio)
    result = select_personal(pool, preferences, {}, NOW)
    assert len(result["items"]) == 8 and result["conference_actual"] == expected
    assert result["latest_actual"] == 8 - expected and not result["warnings"]
    assert len({item["paper_id"] for item in result["items"]}) == 8


def test_personal_shortage_is_filled_without_relabelling_or_inventing_papers():
    pool = [candidate(1, conference=True, age=1000)] + [candidate(i + 2) for i in range(5)]
    result = select_personal(pool, DailyPreferences(keywords=["RAG"], paper_count=5, conference_ratio=.8), {}, NOW)
    assert len(result["items"]) == 5
    assert result["conference_target"] == 4 and result["conference_actual"] == 1
    assert result["latest_actual"] == 4 and result["warnings"]


def test_archive_fills_shortage_without_inflating_latest_count():
    preferences = DailyPreferences(keywords=["RAG"], paper_count=3, conference_ratio=.3)
    pool = [candidate(1, age=1), candidate(2, age=73), candidate(3, age=90 * 24 + 1)]
    result = select_personal(pool, preferences, {}, NOW, include_archive=True)
    assert result["latest_actual"] == 1 and result["archive_actual"] == 1
    assert [item["selection_kind"] for item in result["items"]] == ["latest", "archive"]
    assert result["conference_actual"] == 0


def test_null_conference_fields_do_not_abort_other_records():
    assert conference_name({"venue": None, "publicationVenue": {"name": None}}) is None
    assert conference_name({"venue": None, "publicationVenue": {"name": "ICML"}}) == "ICML"


def test_openalex_backup_requires_proceedings_and_excludes_findings():
    item = {"id": "https://openalex.org/W123", "display_name": "Paper", "publication_year": NOW.year,
            "primary_location": {"raw_type": "proceedings-article", "source": {"display_name": "ICML"}},
            "abstract_inverted_index": {"merge": [1], "model": [0]}}
    assert openalex_conference_record(item, NOW)["abstract"] == "model merge"
    item["primary_location"]["source"]["display_name"] = "Findings of ACL"
    assert openalex_conference_record(item, NOW) is None


def test_old_unverified_unrelated_and_unsupported_venues_are_excluded():
    pool = [candidate(1, age=73), candidate(2, verified=False),
            candidate(3, title="Computer vision", age=1),
            candidate(4, conference=True, age=1000, venue_source=False)]
    pool[2]["abstract"] = "Image recognition"
    result = select_personal(pool, DailyPreferences(keywords=["RAG"], paper_count=8), {}, NOW)
    assert result["items"] == [] and result["warnings"]


@pytest.mark.parametrize("patch", [{"keywords": [" "]}, {"keywords": [123]}, {"keywords": ["a" * 81]},
                                   {"paper_count": 0}, {"paper_count": 51}, {"conference_ratio": 1.01}])
def test_preferences_reject_invalid_input(patch):
    with pytest.raises(ValidationError):
        DailyPreferences.model_validate({"keywords": ["RAG"], **patch})


def test_keywords_are_trimmed_and_deduplicated():
    assert DailyPreferences(keywords=[" RAG ", "RAG", "", "Agent"]).keywords == ["RAG", "Agent"]
    assert keyword_match("Graph neural network", "", ["RAG"]) == 0
    assert keyword_match("Fragment analysis", "", ["RAG"]) == 0
    assert keyword_match("检索增强生成研究", "", ["检索增强生成"]) == 1
    assert keyword_match("RAG retrieval evaluation", "", ["检索增强生成"]) == 1


@pytest.mark.parametrize("venue", ["ICML Workshop", "Findings of ACL", "CVPR Workshops", "arXiv.org"])
def test_conference_labels_never_promote_workshops_findings_or_preprints(venue):
    assert conference_name({"venue": venue, "publicationTypes": ["Conference"]}) is None


def test_conference_record_uses_metadata_not_title_and_preserves_unknown_submission_date():
    item = {"paperId": "a" * 40, "title": "An ICML RAG paper", "abstract": "RAG evaluation",
            "venue": "International Conference on Machine Learning", "publicationTypes": ["Conference"],
            "year": 2025, "externalIds": {"ArXiv": "2501.12345"}, "authors": [{"name": "Public Author"}]}
    record = conference_record(item, NOW)
    assert record["venue"] == "ICML" and record["arxiv_id"] == "2501.12345"
    assert record["first_date_verified"] is False and "first_submitted_at" not in record
    assert conference_record({**item, "venue": "Unknown conference"}, NOW) is None


def test_source_failure_is_explicit_and_queries_cannot_inject_boolean_operators():
    class PublicFetcher:
        def __init__(self):
            self.params = []
        def get(self, url, params):
            self.params.append(params)
            raise RuntimeError("source unavailable")
        def json(self, url, params):
            self.params.append(params)
            raise RuntimeError("source unavailable")
    fetch = PublicFetcher()
    warnings, ids = discover_personal(fetch, "team",
        DailyPreferences(keywords=['RAG" OR all:*'], paper_count=5), NOW)
    assert len(warnings) == 3 and not ids
    assert 'all:*' not in str(fetch.params)
    assert "publicationTypes" in fetch.params[1]

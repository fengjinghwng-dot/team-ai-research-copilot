from decimal import Decimal
from types import SimpleNamespace

import pytest

from copilot.pricing import deepseek_flash_upper
from copilot.weekly import group_by_topics


def test_peak_cost_estimate_accounts_for_cache_without_changing_the_invoice():
    assert deepseek_flash_upper(1_000_000, 100_000) == Decimal('2.8')
    assert deepseek_flash_upper(1_000_000, 100_000, 500_000) == Decimal('1.82')
    with pytest.raises(ValueError):
        deepseek_flash_upper(10, 5, 20)


def test_topic_fallback_requires_distinct_related_papers():
    items = [SimpleNamespace(paper_id=str(i)) for i in range(4)]
    features = {'0': {'RAG': .8}, '1': {'RAG': .6}, '2': {'Agent': .9}, '3': {}}
    groups = group_by_topics(items, features, ['RAG', 'Agent'])
    assert [[item.paper_id for item in group] for group in groups] == [['0', '1']]

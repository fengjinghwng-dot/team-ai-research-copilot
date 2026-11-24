import pytest

from copilot.analyze import validate_evidence
from copilot.citations import ReferencedReport, evidence_ledger, resolve_references


def test_fulltext_reference_ids_resolve_to_exact_source_quotes():
    sections = {'S1': 'We introduce a retrieval model. Our model improves controlled evaluation accuracy.',
                'S2': 'The experiment compares two retrieval baselines. Training uses public data.'}
    ledger = evidence_ledger(sections)
    assert ledger
    for item in ledger.values():
        assert item['quote'] in ' '.join(sections[item['anchor']].split()) and len(item['quote']) >= 16
    report = ReferencedReport(summary='检索模型', innovation='对照实验', methods=[],
        paper_facts=[{'statement':'提出检索模型', 'evidence':{'evidence_id':'E0'}}],
        critical_gaps=[], testable_hypotheses=[], reviewer_view='需继续人工评估')
    resolved = resolve_references(report, ledger)
    validate_evidence(resolved, sections)
    assert resolved.paper_facts[0].evidence.quote == ledger['E0']['quote']
    report.paper_facts[0].evidence.evidence_id = 'fabricated'
    with pytest.raises(ValueError, match='Unknown evidence'):
        resolve_references(report, ledger)

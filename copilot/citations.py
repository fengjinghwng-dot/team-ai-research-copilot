"""Reference IDs bind full-text evidence to excerpts extracted from the supplied source."""
import re

from .schemas import Evidence, Fact, Gap, Hypothesis, PaperReport, Strict


class EvidenceRef(Strict):
    evidence_id: str


class ReferencedFact(Fact):
    evidence: EvidenceRef


class ReferencedGap(Gap):
    evidence: EvidenceRef


class ReferencedHypothesis(Hypothesis):
    evidence: EvidenceRef


class ReferencedReport(PaperReport):
    methods: list[ReferencedFact]
    paper_facts: list[ReferencedFact]
    critical_gaps: list[ReferencedGap]
    testable_hypotheses: list[ReferencedHypothesis]


def evidence_ledger(sections: dict[str, str], limit: int = 96):
    buckets = []
    terms = re.compile(r'\b(we|our|method|results?|model|propos\w*|experiment|accuracy|limitation|baseline|training|evaluation)\b', re.I)
    for anchor, text in sections.items():
        normalized = ' '.join(text.split())
        sentences = [value for value in re.split(r'(?<=[.!?])\s+', normalized) if 16 <= len(value) <= 600]
        if not sentences and len(normalized) >= 16:
            sentences = [normalized[:500]]
        ranked = sorted(enumerate(sentences), key=lambda item: (-len(terms.findall(item[1])), item[0]))
        buckets.append((anchor, [value for _, value in ranked[:12]]))
    ledger, seen = {}, set()
    for index in range(12):
        for anchor, sentences in buckets:
            if index >= len(sentences) or sentences[index] in seen:
                continue
            quote = sentences[index]
            seen.add(quote)
            ledger[f'E{len(ledger)}'] = {'anchor': anchor, 'quote': quote}
            if len(ledger) >= limit:
                return ledger
    return ledger


def resolve_references(report: ReferencedReport, ledger: dict) -> PaperReport:
    payload = report.model_dump()
    for field in ['methods', 'paper_facts', 'critical_gaps', 'testable_hypotheses']:
        for item in payload[field]:
            reference = item['evidence']['evidence_id']
            if reference not in ledger:
                raise ValueError('Unknown evidence reference')
            item['evidence'] = Evidence.model_validate(ledger[reference]).model_dump()
    return PaperReport.model_validate(payload)

"""Prepare a public, unlabelled review set without invoking a model."""
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from .db import session
from .fetch import Fetcher
from .models import Paper, TeamPaper
from .parse import fulltext


def prepare_candidates(team_id: UUID, destination: Path, limit: int = 10, fetch_count: int = 3):
    with session() as db:
        papers = db.scalars(select(Paper).join(TeamPaper, TeamPaper.paper_id == Paper.id).where(
            TeamPaper.team_id == team_id, Paper.first_date_verified.is_(True))
            .order_by(TeamPaper.score.desc(), Paper.first_submitted_at.desc()).limit(limit)).all()
    fetch = Fetcher()
    rows = []
    for index, paper in enumerate(papers):
        document = fulltext(paper, fetch) if index < fetch_count else None
        rows.append({'paper_id': paper.arxiv_id or str(paper.id), 'paper_uuid': str(paper.id),
            'paper_version': paper.arxiv_version, 'title': paper.title, 'source_url': paper.source_url,
            'source_kind': document.kind if document else 'not_fetched',
            'available_anchors': list(document.sections)[:30] if document else [],
            'source_characters': sum(len(value) for value in document.sections.values()) if document else 0,
            'truncated': document.truncated if document else False,
            'expert_innovation': [], 'expert_limitations': [], 'required_anchors': [], 'forbidden_claims': [],
            'human_scores': None, 'status': 'unlabelled',
            'selection_note': 'Automatically selected candidates; expert representativeness not yet confirmed'})
        print(json.dumps({'prepared': index + 1, 'source_kind': rows[-1]['source_kind']}, ensure_ascii=False), flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    return {'candidates': len(rows), 'fulltexts_cached': sum(row['source_kind'] != 'not_fetched' for row in rows),
            'human_reviewed': 0, 'llm_calls': 0}

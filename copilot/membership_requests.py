from sqlalchemy import update

from .models import JoinRequest, utcnow


def resolve_for_member(db, team_id, user_id, reviewer_id):
    """An explicit admin grant or accepted invitation also resolves this user's pending application."""
    db.execute(update(JoinRequest).where(JoinRequest.team_id == team_id, JoinRequest.user_id == user_id,
        JoinRequest.status == "pending").values(status="approved", reviewed_at=utcnow(), reviewed_by=reviewer_id))


def cancel_for_removed_member(db, team_id, user_id, reviewer_id):
    db.execute(update(JoinRequest).where(JoinRequest.team_id == team_id, JoinRequest.user_id == user_id,
        JoinRequest.status == "pending").values(status="cancelled", reviewed_at=utcnow(), reviewed_by=reviewer_id))

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .models import Invitation, Membership, Team, utcnow


def accept_pending(db, user):
    """Bind an invitation to the canonical email from a validated Auth identity, never form metadata."""
    now = utcnow()
    pending = db.scalars(select(Invitation).where(
        Invitation.email == user.email.strip().lower(), Invitation.accepted_at.is_(None),
        Invitation.revoked_at.is_(None), Invitation.expires_at > now).order_by(Invitation.team_id)).all()
    for item in pending:
        # Same lock order as invitation creation, revocation, and membership changes.
        db.scalar(select(Team).where(Team.id == item.team_id).with_for_update())
        active = db.scalar(select(Invitation).where(Invitation.id == item.id,
            Invitation.accepted_at.is_(None), Invitation.revoked_at.is_(None),
            Invitation.expires_at > now).with_for_update().execution_options(populate_existing=True))
        if not active:
            continue
        db.execute(insert(Membership).values(team_id=item.team_id, user_id=user.id, role="member", interests={})
                   .on_conflict_do_nothing())  # Existing administrator roles must never be overwritten.
        active.accepted_at, active.accepted_by = now, user.id
    db.flush()


def admin_count(db, team_id):
    return db.scalar(select(func.count()).select_from(Membership).where(
        Membership.team_id == team_id, Membership.role == "admin"))

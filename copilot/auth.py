from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Membership, User

bearer = HTTPBearer(auto_error=False)


@lru_cache
def jwks():
    url = settings().supabase_url.rstrip("/")
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", cache_keys=True,
                          lifespan=300, timeout=10)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(401, "Bearer access token required", headers={"WWW-Authenticate": "Bearer"})
    if not settings().supabase_url:
        raise HTTPException(503, "SSO has not been configured")
    try:
        key = jwks().get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(credentials.credentials, key.key, algorithms=["ES256", "RS256"],
                            audience="authenticated", issuer=settings().supabase_url.rstrip("/") + "/auth/v1",
                            options={"require": ["exp", "iat", "sub", "aud", "iss"]})
        uid = UUID(claims["sub"])
        email = claims.get("email")
        if not email or claims.get("is_anonymous"):
            raise ValueError("A verified, non-anonymous account is required")
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid or expired access token") from None
    user = db.get(User, uid)
    if not user:
        # Registration grants no team access. Only a team admin can add memberships.
        user = User(id=uid, email=email, display_name="")
        db.add(user)
        db.flush()
    return user


@dataclass
class TeamContext:
    team_id: UUID
    user: User
    membership: Membership


def team_member(team_id: UUID = Path(), user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> TeamContext:
    membership = db.get(Membership, (team_id, user.id))
    if not membership:
        raise HTTPException(403, "Team membership required")
    return TeamContext(team_id, user, membership)


def team_admin(ctx: TeamContext = Depends(team_member)) -> TeamContext:
    if ctx.membership.role != "admin":
        raise HTTPException(403, "Team administrator required")
    return ctx

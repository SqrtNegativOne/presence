"""
JWT session tokens — HS256, short-lived.

The secret is read from PRESENCE_JWT_SECRET. In development we fall back to a
fixed value so the app boots out of the box; the lifespan logs a warning if
that fallback is in use, and the dev secret is rotated on each container build.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from loguru import logger

ALGORITHM = "HS256"
DEFAULT_TTL_HOURS = 24 * 7

_DEV_FALLBACK_SECRET = "dev-only-not-for-production-" + secrets.token_hex(8)


def _secret() -> str:
    s = os.environ.get("PRESENCE_JWT_SECRET")
    if s:
        return s
    return _DEV_FALLBACK_SECRET


def warn_if_dev_secret() -> None:
    if not os.environ.get("PRESENCE_JWT_SECRET"):
        logger.warning(
            "PRESENCE_JWT_SECRET not set — using an in-memory dev secret. "
            "All sessions are invalidated on every restart. Set the env var in production."
        )


def issue_session_token(user_id: int, email: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ttl_hours)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, _secret(), algorithm=ALGORITHM)
    return token, expires


def decode_session_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as e:
        logger.debug(f"JWT decode failed: {e}")
        return None

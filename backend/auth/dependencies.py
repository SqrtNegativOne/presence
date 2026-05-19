"""
FastAPI dependencies that resolve the current user from an Authorization header.

Tokens are validated two ways:
1. JWT decode (cheap, no DB hit) — confirms signature + expiry.
2. Session row lookup — confirms the token wasn't revoked (logout).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

import database
from .jwt import decode_session_token


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def _resolve_user(authorization: Optional[str]) -> Optional[dict]:
    token = _extract_token(authorization)
    if not token:
        return None
    payload = decode_session_token(token)
    if not payload:
        return None
    session = database.get_session(token)
    if not session:
        return None
    user = database.get_user(session["user_id"])
    return user


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    user = _resolve_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    return _resolve_user(authorization)

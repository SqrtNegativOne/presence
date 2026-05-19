"""
routers/auth.py — Google sign-in, demo sign-in, /me, logout.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from loguru import logger
from pydantic import BaseModel

import database
from auth.dependencies import get_current_user
from auth.google import verify_google_id_token
from auth.jwt import decode_session_token, issue_session_token

DEMO_EMAIL = "demo@presence.local"

router = APIRouter(prefix="/api/auth", tags=["auth"])


class GoogleSignInRequest(BaseModel):
    credential: str  # the Google ID token (a JWT)


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture_url": user.get("picture_url"),
        "is_demo": bool(user.get("is_demo")),
        "preferred_recognizer": user.get("preferred_recognizer"),
    }


def _issue_session(user: dict) -> dict:
    token, expires = issue_session_token(user["id"], user["email"])
    database.create_session(token, user["id"], expires.replace(tzinfo=None).isoformat())
    return {
        "token": token,
        "expires_at": expires.isoformat(),
        "user": _public_user(user),
    }


@router.post("/google")
async def sign_in_with_google(body: GoogleSignInRequest):
    """Exchange a Google ID token for a Presence session token."""
    try:
        claims = verify_google_id_token(body.credential)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = database.upsert_user(
        google_sub=claims["sub"],
        email=claims["email"],
        name=claims.get("name") or claims["email"].split("@")[0],
        picture_url=claims.get("picture"),
        is_demo=False,
    )
    logger.info(f"Google sign-in: {user['email']}")
    return _issue_session(user)


@router.post("/demo")
async def sign_in_as_demo():
    """One-click demo sign-in. No Google credentials required."""
    user = database.get_user_by_email(DEMO_EMAIL)
    if not user:
        user = database.upsert_user(
            google_sub=None, email=DEMO_EMAIL, name="Demo Teacher",
            picture_url=None, is_demo=True,
        )
    logger.info(f"Demo sign-in: {user['email']}")
    return _issue_session(user)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return _public_user(user)


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    """Revoke the bearer token on the server. Always returns 200 (idempotent)."""
    if not authorization:
        return {"ok": True}
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        # No need to verify the JWT — deleting an unknown row is a no-op.
        database.delete_session(token)
    return {"ok": True}

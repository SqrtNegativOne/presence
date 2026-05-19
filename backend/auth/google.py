"""
Google ID token verification.

The frontend uses Google Identity Services to get an ID token (a JWT signed by
Google). We hand it to google-auth which verifies the signature against
Google's public keys and the `aud` claim against our PRESENCE_GOOGLE_CLIENT_ID.

If PRESENCE_GOOGLE_CLIENT_ID is unset we still parse the token but skip the
audience check — handy when developing without OAuth credentials yet, NOT safe
for production. We log a warning in that case.
"""
from __future__ import annotations

import os
from typing import Optional

from loguru import logger


def google_client_id() -> Optional[str]:
    return os.environ.get("PRESENCE_GOOGLE_CLIENT_ID") or None


def verify_google_id_token(id_token_str: str) -> dict:
    """Return the decoded ID-token claims dict, or raise ValueError on failure.

    Important claims for us: sub (Google user id), email, name, picture, email_verified.
    """
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token as g_id_token

    client_id = google_client_id()
    request = g_requests.Request()
    try:
        if client_id:
            claims = g_id_token.verify_oauth2_token(id_token_str, request, client_id)
        else:
            logger.warning(
                "PRESENCE_GOOGLE_CLIENT_ID not set — verifying Google token without "
                "audience check. Do NOT use this in production."
            )
            claims = g_id_token.verify_oauth2_token(id_token_str, request)
    except ValueError as e:
        raise ValueError(f"Invalid Google ID token: {e}") from e

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Unexpected token issuer.")
    if not claims.get("email"):
        raise ValueError("Google token has no email claim.")
    return claims

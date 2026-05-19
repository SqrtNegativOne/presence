"""Auth subpackage: Google OAuth verification, JWT sessions, FastAPI deps."""
from .dependencies import get_current_user, optional_user
from .jwt import issue_session_token, decode_session_token
from .google import verify_google_id_token

__all__ = [
    "get_current_user",
    "optional_user",
    "issue_session_token",
    "decode_session_token",
    "verify_google_id_token",
]

"""
config.py — Runtime configuration for the Presence backend.

Values are read from the environment. The same simple `.env` loading that
`database.py` performs is replicated here so this module is correct even when
imported before `database` (the files are idempotent and never override values
already present in the real environment).
"""

import os

from fastapi import HTTPException


def _load_env_file() -> None:
    for candidate in [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
    ]:
        if os.path.isfile(candidate):
            try:
                with open(candidate, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass


_load_env_file()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# When false, cloud (server-side InsightFace) endpoints are disabled and the
# heavy ML dependencies are never imported. Local/browser mode stays available.
CLOUD_MODE_ENABLED = _bool("CLOUD_MODE_ENABLED", True)

# Comma-separated CORS allow-list.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]


def require_cloud_mode() -> None:
    """Raise 503 if this deployment has cloud mode disabled."""
    if not CLOUD_MODE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cloud mode is disabled on this deployment. Use local (browser) mode."
            ),
        )

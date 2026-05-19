"""
seed_demo.py — Create the demo user and enrol the four sample students.

Runs at startup (idempotent). Uses the default recognizer (insightface_l) to
compute embeddings from the bundled portrait images in backend/demo_assets/.

Failure here must not block backend startup — the warning is logged and the
demo button will simply have nothing to show.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

import database
from services.face_service import encode_single_face, invalidate_cache
from recognizers import default_name

DEMO_EMAIL = "demo@presence.local"
DEMO_CLASS = "Demo-Class"
DEMO_ASSETS = Path(__file__).parent / "demo_assets" / "students"

# Roll numbers are stable so re-running the seeder doesn't create duplicates.
DEMO_STUDENTS = [
    ("Alice Chen",    "DEMO-001", "alice.jpg"),
    ("Bob Patel",     "DEMO-002", "bob.jpg"),
    ("Carol Nguyen",  "DEMO-003", "carol.jpg"),
    ("Dave Okafor",   "DEMO-004", "dave.jpg"),
]


def ensure_demo_user() -> dict:
    user = database.get_user_by_email(DEMO_EMAIL)
    if user:
        return user
    return database.upsert_user(
        google_sub=None, email=DEMO_EMAIL, name="Demo Teacher",
        picture_url=None, is_demo=True,
    )


def seed() -> None:
    """Create the demo user + enrol all demo students using the default recognizer."""
    user = ensure_demo_user()
    user_id = user["id"]
    recognizer_name = default_name()

    existing = {s["roll_number"]: s for s in database.get_user_students(user_id)}

    for name, roll, filename in DEMO_STUDENTS:
        if roll in existing and existing[roll]["recognizer_name"] == recognizer_name:
            logger.debug(f"Demo student already enrolled: {roll}")
            continue

        path = DEMO_ASSETS / filename
        if not path.exists():
            logger.warning(f"Demo asset missing: {path}")
            continue

        try:
            with open(path, "rb") as f:
                image_bytes = f.read()
            embedding, _ = encode_single_face(image_bytes, recognizer_name)
        except Exception as e:
            logger.warning(f"Could not encode demo student {roll}: {e}")
            continue

        # If a row already exists with a different recognizer, leave it alone
        # (the per-recognizer matching code will only use the right one).
        if roll in existing:
            logger.info(f"Demo student {roll} already exists with a different recognizer; skipping.")
            continue

        try:
            database.insert_student(user_id, name, roll, DEMO_CLASS, embedding, recognizer_name)
        except Exception as e:
            logger.warning(f"Failed to insert demo student {roll}: {e}")
            continue

    invalidate_cache(user_id, recognizer_name)
    logger.success(f"Demo seeder complete (user id={user_id}).")

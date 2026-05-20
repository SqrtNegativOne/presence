"""
seed_demo.py — Create the demo user and enrol every bundled demo class.

Runs at startup (idempotent). Uses the default recognizer (insightface_l) to
compute embeddings from the bundled portrait images in backend/demo_assets/.

Failure here must not block backend startup — the warning is logged and the
demo button will simply have fewer classes to show.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

import database
from services.face_service import encode_single_face, invalidate_cache
from recognizers import default_name

DEMO_EMAIL = "demo@presence.local"
DEMO_ASSETS = Path(__file__).parent / "demo_assets"


@dataclass(frozen=True)
class DemoClass:
    class_name: str
    display_name: str         # shown in the UI; can differ from class_name
    description: str          # one-line hint for the UI
    asset_dir: Path           # holds students/ + group.jpg
    students: tuple[tuple[str, str, str], ...]  # (name, roll, filename)


DEMO_CLASSES: tuple[DemoClass, ...] = (
    DemoClass(
        class_name="Demo-Class",
        display_name="Synthetic Class",
        description="Four CC0 AI-generated faces. Always recognizable.",
        asset_dir=DEMO_ASSETS / "synthetic",
        students=(
            ("Alice Chen",   "DEMO-001", "alice.jpg"),
            ("Bob Patel",    "DEMO-002", "bob.jpg"),
            ("Carol Nguyen", "DEMO-003", "carol.jpg"),
            ("Dave Okafor",  "DEMO-004", "dave.jpg"),
        ),
    ),
    DemoClass(
        class_name="Apollo-11",
        display_name="Apollo 11 Crew",
        description="Real NASA portraits (public domain). Demonstrates real-photo accuracy.",
        asset_dir=DEMO_ASSETS / "apollo11",
        students=(
            ("Neil Armstrong",  "NASA-001", "armstrong.jpg"),
            ("Buzz Aldrin",     "NASA-002", "aldrin.jpg"),
            ("Michael Collins", "NASA-003", "collins.jpg"),
        ),
    ),
)


def demo_group_photo(class_name: str) -> Path | None:
    """Return the path to the group photo for a given demo class, or None."""
    for cls in DEMO_CLASSES:
        if cls.class_name == class_name:
            p = cls.asset_dir / "group.jpg"
            return p if p.exists() else None
    return None


def list_demo_classes() -> list[dict]:
    """For the UI: name + brief description + whether the group photo is bundled."""
    return [{
        "class_name": c.class_name,
        "display_name": c.display_name,
        "description": c.description,
        "student_count": len(c.students),
        "has_group_photo": (c.asset_dir / "group.jpg").exists(),
    } for c in DEMO_CLASSES]


def ensure_demo_user() -> dict:
    user = database.get_user_by_email(DEMO_EMAIL)
    if user:
        return user
    return database.upsert_user(
        google_sub=None, email=DEMO_EMAIL, name="Demo Teacher",
        picture_url=None, is_demo=True,
    )


def seed() -> None:
    """Create the demo user + enrol every bundled class with the default recognizer."""
    user = ensure_demo_user()
    user_id = user["id"]
    recognizer_name = default_name()

    existing = {s["roll_number"]: s for s in database.get_user_students(user_id)}

    for cls in DEMO_CLASSES:
        for name, roll, filename in cls.students:
            if roll in existing and existing[roll]["recognizer_name"] == recognizer_name:
                logger.debug(f"Demo student already enrolled: {roll}")
                continue
            if roll in existing:
                logger.info(f"Demo student {roll} exists with a different recognizer; skipping.")
                continue

            path = cls.asset_dir / "students" / filename
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

            try:
                database.insert_student(user_id, name, roll, cls.class_name,
                                        embedding, recognizer_name)
            except Exception as e:
                logger.warning(f"Failed to insert demo student {roll}: {e}")
                continue

    invalidate_cache(user_id, recognizer_name)
    logger.success(f"Demo seeder complete (user id={user_id}).")

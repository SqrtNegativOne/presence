"""
database.py — SQLite connection and all DB operations.

Schema:
    users               — owners of data (Google account or built-in demo)
    sessions            — opaque session tokens, mapped to a user
    students            — face embeddings, scoped per user + recognizer
    attendance_records  — one row per student per (date, class)

Still no ORM: every query is a plain string. Embeddings are pickled numpy
arrays in a BLOB column.
"""
from __future__ import annotations

import pickle
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "presence.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables and run lightweight migrations on existing DBs."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub           TEXT    UNIQUE,
                email                TEXT    UNIQUE NOT NULL,
                name                 TEXT    NOT NULL,
                picture_url          TEXT,
                is_demo              INTEGER NOT NULL DEFAULT 0,
                preferred_recognizer TEXT    NOT NULL DEFAULT 'insightface_l',
                created_at           TEXT    DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT    PRIMARY KEY,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
                expires_at  TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

            CREATE TABLE IF NOT EXISTS students (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name            TEXT    NOT NULL,
                roll_number     TEXT    NOT NULL,
                class_name      TEXT    NOT NULL,
                face_embedding  BLOB    NOT NULL,
                recognizer_name TEXT    NOT NULL DEFAULT 'insightface_l',
                enrolled_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, roll_number)
            );
            CREATE INDEX IF NOT EXISTS idx_students_user ON students(user_id);
            CREATE INDEX IF NOT EXISTS idx_students_user_rec
                ON students(user_id, recognizer_name);

            CREATE TABLE IF NOT EXISTS attendance_records (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                class_name      TEXT    NOT NULL,
                attendance_date TEXT    NOT NULL,
                status          TEXT    NOT NULL,    -- "present" | "absent"
                similarity      REAL,
                recorded_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, student_id, attendance_date, class_name)
            );
            CREATE INDEX IF NOT EXISTS idx_attendance_lookup
                ON attendance_records(user_id, class_name, attendance_date);
        """)

        # --- light-touch migration for pre-auth databases ---
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
        if "user_id" in cols and "recognizer_name" not in cols:
            # very old students table — add the column
            conn.execute("ALTER TABLE students ADD COLUMN recognizer_name TEXT NOT NULL DEFAULT 'insightface_l'")
            logger.info("Migrated: added recognizer_name to students")
        conn.commit()
    logger.info(f"Database ready at {DB_PATH}")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def upsert_user(google_sub: Optional[str], email: str, name: str,
                picture_url: Optional[str], is_demo: bool = False) -> dict:
    """Insert or update a user. Returns the full row."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE google_sub = ? OR email = ?",
            (google_sub, email),
        ).fetchone()
        if existing is None:
            cur = conn.execute(
                "INSERT INTO users (google_sub, email, name, picture_url, is_demo) "
                "VALUES (?, ?, ?, ?, ?)",
                (google_sub, email, name, picture_url, 1 if is_demo else 0),
            )
            user_id = cur.lastrowid
        else:
            user_id = existing["id"]
            conn.execute(
                "UPDATE users SET google_sub = COALESCE(?, google_sub), "
                "name = ?, picture_url = COALESCE(?, picture_url) WHERE id = ?",
                (google_sub, name, picture_url, user_id),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)


def get_user(user_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def set_user_recognizer(user_id: int, recognizer_name: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE users SET preferred_recognizer = ? WHERE id = ?",
                     (recognizer_name, user_id))
        conn.commit()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def create_session(token: str, user_id: int, expires_at_iso: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at_iso),
        )
        conn.commit()


def get_session(token: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT s.token, s.user_id, s.expires_at, u.email, u.name, u.picture_url, "
            "       u.is_demo, u.preferred_recognizer "
            "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
def insert_student(user_id: int, name: str, roll_number: str, class_name: str,
                   embedding: np.ndarray, recognizer_name: str) -> int:
    blob = pickle.dumps(embedding.astype(np.float32, copy=False))
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO students (user_id, name, roll_number, class_name, "
            "                      face_embedding, recognizer_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, roll_number, class_name, blob, recognizer_name),
        )
        conn.commit()
        logger.info(f"Enrolled student user={user_id} {name} ({roll_number}) "
                    f"class={class_name} recognizer={recognizer_name}")
        return cur.lastrowid


def get_user_students(user_id: int, class_name: Optional[str] = None) -> list[dict]:
    with get_connection() as conn:
        if class_name:
            rows = conn.execute(
                "SELECT id, name, roll_number, class_name, recognizer_name, enrolled_at "
                "FROM students WHERE user_id = ? AND class_name = ? ORDER BY name",
                (user_id, class_name),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, roll_number, class_name, recognizer_name, enrolled_at "
                "FROM students WHERE user_id = ? ORDER BY name",
                (user_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_user_students_with_embeddings(user_id: int, recognizer_name: str) -> list[dict]:
    """Return only students whose embeddings were computed by the same recognizer.

    Different recognizers produce non-comparable embeddings, so the matcher
    must restrict itself to homogeneous rows.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, roll_number, class_name, face_embedding "
            "FROM students WHERE user_id = ? AND recognizer_name = ?",
            (user_id, recognizer_name),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["face_embedding"] = pickle.loads(d["face_embedding"])
        result.append(d)
    return result


def delete_student(user_id: int, student_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM students WHERE id = ? AND user_id = ?",
                           (student_id, user_id))
        conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Attendance records
# ---------------------------------------------------------------------------
def record_attendance(user_id: int, student_id: int, class_name: str,
                      attendance_date: str, status: str,
                      similarity: Optional[float]) -> None:
    """Insert or replace an attendance row (idempotent per student/date/class)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO attendance_records "
            "  (user_id, student_id, class_name, attendance_date, status, similarity) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, student_id, attendance_date, class_name) DO UPDATE SET "
            "  status = excluded.status, similarity = excluded.similarity, "
            "  recorded_at = CURRENT_TIMESTAMP",
            (user_id, student_id, class_name, attendance_date, status, similarity),
        )
        conn.commit()


def list_attendance(user_id: int, class_name: str, attendance_date: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.name, s.roll_number, s.class_name, a.attendance_date, "
            "       a.status, a.similarity "
            "FROM attendance_records a JOIN students s ON s.id = a.student_id "
            "WHERE a.user_id = ? AND a.class_name = ? AND a.attendance_date = ? "
            "ORDER BY s.name",
            (user_id, class_name, attendance_date),
        ).fetchall()
    return [dict(r) for r in rows]

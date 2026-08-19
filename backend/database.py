"""
database.py — SQLite connection and all DB operations.

We use Python's built-in sqlite3 module, so there is nothing extra to install.
Embeddings (512-dimension numpy arrays) are stored as BLOBs using pickle.
"""

import pickle
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

# Always resolve the DB path relative to this file, inside the data/ folder.
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "presence.db"


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection with row_factory so rows behave like dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us do row["name"] instead of row[0]
    return conn


def init_db() -> None:
    """Create tables if they don't already exist. Called once at startup."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL,
                roll_number     TEXT    NOT NULL UNIQUE,
                class_name      TEXT    NOT NULL,
                face_embedding  BLOB    NOT NULL,
                enrolled_at     TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_class_name ON students(class_name);")
        conn.commit()
    logger.info(f"Database ready at {DB_PATH}")


# ---------------------------------------------------------------------------
# Student CRUD
# ---------------------------------------------------------------------------

def insert_student(name: str, roll_number: str, class_name: str, embedding: np.ndarray) -> int:
    """
    Persist a new student. Returns the new row's id.
    embedding: float32 numpy array of shape (512,)
    """
    blob = pickle.dumps(embedding)  # numpy array → raw bytes
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO students (name, roll_number, class_name, face_embedding) VALUES (?, ?, ?, ?)",
            (name, roll_number, class_name, blob),
        )
        conn.commit()
        logger.info(f"Enrolled student: {name} ({roll_number}), class={class_name}")
        return cur.lastrowid


def get_all_students(class_name: Optional[str] = None) -> list[dict]:
    """
    Return all students, optionally filtered by class_name.
    The face_embedding BLOB is NOT returned here (it's large and not needed for listing).
    """
    with get_connection() as conn:
        if class_name:
            rows = conn.execute(
                "SELECT id, name, roll_number, class_name, enrolled_at FROM students WHERE class_name = ? ORDER BY name",
                (class_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, name, roll_number, class_name, enrolled_at FROM students ORDER BY name"
            ).fetchall()
    return [dict(row) for row in rows]


def get_all_students_with_embeddings(class_name: str) -> list[dict]:
    """
    Return all students in a specific class including their embeddings (for attendance matching).
    Embeddings are decoded back to numpy arrays here.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, roll_number, class_name, face_embedding FROM students WHERE class_name = ?",
            (class_name,)
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["face_embedding"] = pickle.loads(d["face_embedding"])  # bytes → numpy array
        result.append(d)
    return result


def get_students_by_roll_numbers(roll_numbers: list[str]) -> list[dict]:
    """Return specific students by their roll numbers."""
    if not roll_numbers:
        return []
    
    # Create a parameter placeholder string like "?, ?, ?"
    placeholders = ",".join("?" * len(roll_numbers))
    query = f"SELECT name, roll_number, class_name FROM students WHERE roll_number IN ({placeholders})"
    
    with get_connection() as conn:
        rows = conn.execute(query, roll_numbers).fetchall()
    return [dict(row) for row in rows]


def delete_student(student_id: int) -> bool:
    """Delete a student by id. Returns True if a row was deleted."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
    deleted = cur.rowcount > 0
    if deleted:
        logger.info(f"Deleted student id={student_id}")
    else:
        logger.warning(f"Delete requested for non-existent student id={student_id}")
    return deleted

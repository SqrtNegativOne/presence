"""
database.py — SQLite connection and all DB operations.

We use Python's built-in sqlite3 module, so there is nothing extra to install.
Embeddings (512-dimension numpy arrays) are stored as BLOBs using raw float32 bytes.
"""

import sqlite3
from pathlib import Path
import os
from typing import Optional

import numpy as np
from loguru import logger

# Always resolve the DB path relative to this file, inside the data/ folder.
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "presence.db")))


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection with row_factory so rows behave like dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name       TEXT    NOT NULL,
                attendance_date  TEXT    NOT NULL,
                photo_hash       TEXT,
                total_faces      INTEGER NOT NULL,
                recognized_count INTEGER NOT NULL,
                unknown_count    INTEGER NOT NULL,
                created_at       TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_class ON attendance_sessions(class_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_date ON attendance_sessions(attendance_date);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_records (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      INTEGER NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
                student_id      INTEGER REFERENCES students(id) ON DELETE SET NULL,
                status          TEXT    NOT NULL CHECK (status IN ('present', 'absent')),
                similarity      REAL,
                face_index      INTEGER,
                UNIQUE(session_id, student_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_session ON attendance_records(session_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_student ON attendance_records(student_id);")
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
    blob = embedding.astype(np.float32).tobytes()  # numpy array → raw bytes (512 * 4 = 2048 bytes)
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
        d["face_embedding"] = np.frombuffer(d["face_embedding"], dtype=np.float32)  # bytes → numpy array
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


# ---------------------------------------------------------------------------
# Attendance Sessions & Records
# ---------------------------------------------------------------------------

def create_attendance_session(
    class_name: str,
    attendance_date: str,
    total_faces: int,
    recognized_count: int,
    unknown_count: int,
    photo_hash: Optional[str] = None,
) -> int:
    """Create an attendance session record and return its ID."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO attendance_sessions (class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count),
        )
        conn.commit()
        session_id = cur.lastrowid
        logger.info(f"Created attendance session id={session_id} for class={class_name}, date={attendance_date}")
        return session_id


def insert_attendance_records(session_id: int, records: list[dict]) -> None:
    """
    Insert attendance records for a session.
    Each record dict contains:
      student_id: Optional[int] (or int)
      status: 'present' | 'absent'
      similarity: Optional[float]
      face_index: Optional[int]
    """
    if not records:
        return
    rows = [
        (
            session_id,
            r.get("student_id"),
            r["status"],
            r.get("similarity"),
            r.get("face_index"),
        )
        for r in records
    ]
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO attendance_records (session_id, student_id, status, similarity, face_index)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    logger.info(f"Inserted {len(records)} attendance records for session id={session_id}")


def get_attendance_history(class_name: Optional[str] = None) -> list[dict]:
    """
    Return past attendance sessions, optionally filtered by class_name.
    Ordered by attendance_date DESC, id DESC.
    """
    with get_connection() as conn:
        if class_name:
            rows = conn.execute(
                """
                SELECT id, class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count, created_at
                FROM attendance_sessions
                WHERE class_name = ?
                ORDER BY attendance_date DESC, id DESC
                """,
                (class_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count, created_at
                FROM attendance_sessions
                ORDER BY attendance_date DESC, id DESC
                """
            ).fetchall()
    return [dict(row) for row in rows]


def get_session_detail(session_id: int) -> Optional[dict]:
    """
    Return full details of an attendance session, including all student records
    joined with student details (name, roll_number).
    """
    with get_connection() as conn:
        session_row = conn.execute(
            """
            SELECT id, class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count, created_at
            FROM attendance_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()

        if not session_row:
            return None

        session_dict = dict(session_row)

        record_rows = conn.execute(
            """
            SELECT 
                r.id,
                r.session_id,
                r.student_id,
                COALESCE(s.name, 'Deleted Student') AS name,
                s.roll_number,
                COALESCE(s.class_name, ?) AS class_name,
                r.status,
                r.similarity,
                r.face_index
            FROM attendance_records r
            LEFT JOIN students s ON r.student_id = s.id
            WHERE r.session_id = ?
            ORDER BY 
                CASE r.status WHEN 'present' THEN 1 ELSE 2 END,
                s.roll_number ASC,
                s.name ASC
            """,
            (session_dict["class_name"], session_id),
        ).fetchall()

        session_dict["records"] = [dict(r) for r in record_rows]
        return session_dict


def get_session_by_class_and_date(class_name: str, attendance_date: str) -> Optional[dict]:
    """Return the latest session detail for a given class and date."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM attendance_sessions
            WHERE class_name = ? AND attendance_date = ?
            ORDER BY id DESC LIMIT 1
            """,
            (class_name, attendance_date),
        ).fetchone()
        if not row:
            return None
        return get_session_detail(row["id"])


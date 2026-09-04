"""
database.py — PostgreSQL connection pool and all DB operations.

We use psycopg (v3) with connection pooling (psycopg_pool.ConnectionPool).
Embeddings (float32 numpy arrays) are stored as BYTEA using raw bytes.
"""

import atexit
import os
from contextlib import contextmanager

import numpy as np
from loguru import logger
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://presence:presence@localhost:5432/presence",
)

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Return the global ConnectionPool instance, initializing it if necessary."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
    return _pool


def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.close()
        _pool = None


atexit.register(close_pool)


def set_database_url(url: str) -> None:
    """Update DATABASE_URL and reset connection pool (useful for tests)."""
    global DATABASE_URL
    close_pool()
    DATABASE_URL = url


@contextmanager
def get_connection():
    """Yield a connection from the pool."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def init_db() -> None:
    """Create PostgreSQL tables and indexes if they don't already exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id              SERIAL PRIMARY KEY,
                    name            TEXT    NOT NULL,
                    roll_number     TEXT    NOT NULL UNIQUE,
                    class_name      TEXT    NOT NULL,
                    model_type      TEXT    NOT NULL DEFAULT 'insightface',
                    face_embedding  BYTEA   NOT NULL,
                    enrolled_at     TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_name);
                CREATE INDEX IF NOT EXISTS idx_students_model ON students(model_type);

                CREATE TABLE IF NOT EXISTS attendance_sessions (
                    id               SERIAL PRIMARY KEY,
                    class_name       TEXT    NOT NULL,
                    attendance_date  DATE    NOT NULL,
                    photo_hash       TEXT,
                    total_faces      INTEGER NOT NULL,
                    recognized_count INTEGER NOT NULL,
                    unknown_count    INTEGER NOT NULL,
                    created_at       TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_class ON attendance_sessions(class_name);
                CREATE INDEX IF NOT EXISTS idx_sessions_date ON attendance_sessions(attendance_date);

                CREATE TABLE IF NOT EXISTS attendance_records (
                    id              SERIAL PRIMARY KEY,
                    session_id      INTEGER NOT NULL REFERENCES attendance_sessions(id) ON DELETE CASCADE,
                    student_id      INTEGER REFERENCES students(id) ON DELETE SET NULL,
                    status          TEXT    NOT NULL CHECK (status IN ('present', 'absent')),
                    similarity      REAL,
                    face_index      INTEGER,
                    UNIQUE(session_id, student_id)
                );
                CREATE INDEX IF NOT EXISTS idx_records_session ON attendance_records(session_id);
                CREATE INDEX IF NOT EXISTS idx_records_student ON attendance_records(student_id);
            """)
        conn.commit()
    logger.info(f"Database ready at {DATABASE_URL}")


# ---------------------------------------------------------------------------
# Student CRUD
# ---------------------------------------------------------------------------


def insert_student(
    name: str,
    roll_number: str,
    class_name: str,
    embedding: np.ndarray,
    model_type: str = "insightface",
) -> int:
    """
    Persist a new student. Returns the new row's id.
    embedding: float32 numpy array (shape (512,) or (128,))
    """
    blob = embedding.astype(np.float32).tobytes()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO students (name, roll_number, class_name, model_type, face_embedding)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (name, roll_number, class_name, model_type, blob),
            )
            row = cur.fetchone()
        conn.commit()
        student_id = row["id"]
        logger.info(
            f"Enrolled student: {name} ({roll_number}), class={class_name}, model={model_type}"
        )
        return student_id


def get_all_students(class_name: str | None = None) -> list[dict]:
    """
    Return all students, optionally filtered by class_name.
    The face_embedding BYTEA is NOT returned here (it's large and not needed for listing).
    """
    with get_connection() as conn, conn.cursor() as cur:
        if class_name:
            cur.execute(
                """
                    SELECT id, name, roll_number, class_name, model_type, enrolled_at
                    FROM students
                    WHERE class_name = %s
                    ORDER BY name
                    """,
                (class_name,),
            )
        else:
            cur.execute(
                """
                    SELECT id, name, roll_number, class_name, model_type, enrolled_at
                    FROM students
                    ORDER BY name
                    """
            )
        rows = cur.fetchall()

    result = []
    for r in rows:
        d = dict(r)
        if hasattr(d.get("enrolled_at"), "isoformat"):
            d["enrolled_at"] = d["enrolled_at"].isoformat()
        result.append(d)
    return result


def get_all_students_with_embeddings(
    class_name: str, model_type: str | None = None
) -> list[dict]:
    """
    Return all students in a specific class including their embeddings (for attendance matching).
    Optionally filters by model_type ('insightface' | 'faceapi').
    Embeddings are decoded back to numpy arrays.
    """
    with get_connection() as conn, conn.cursor() as cur:
        if model_type:
            cur.execute(
                """
                    SELECT id, name, roll_number, class_name, model_type, face_embedding
                    FROM students
                    WHERE class_name = %s AND model_type = %s
                    """,
                (class_name, model_type),
            )
        else:
            cur.execute(
                """
                    SELECT id, name, roll_number, class_name, model_type, face_embedding
                    FROM students
                    WHERE class_name = %s
                    """,
                (class_name,),
            )
        rows = cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["face_embedding"] = np.frombuffer(d["face_embedding"], dtype=np.float32)
        result.append(d)
    return result


def get_students_by_roll_numbers(roll_numbers: list[str]) -> list[dict]:
    """Return specific students by their roll numbers."""
    if not roll_numbers:
        return []

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT name, roll_number, class_name, model_type
                FROM students
                WHERE roll_number = ANY(%s)
                """,
            (roll_numbers,),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def delete_student(student_id: int) -> bool:
    """Delete a student by id. Returns True if a row was deleted."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM students WHERE id = %s", (student_id,))
            deleted = cur.rowcount > 0
        conn.commit()

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
    photo_hash: str | None = None,
) -> int:
    """Create an attendance session record and return its ID."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO attendance_sessions (class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    class_name,
                    attendance_date,
                    photo_hash,
                    total_faces,
                    recognized_count,
                    unknown_count,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        session_id = row["id"]
        logger.info(
            f"Created attendance session id={session_id} for class={class_name}, date={attendance_date}"
        )
        return session_id


def insert_attendance_records(session_id: int, records: list[dict]) -> None:
    """
    Insert attendance records for a session.
    Each record dict contains:
      student_id: Optional[int]
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
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO attendance_records (session_id, student_id, status, similarity, face_index)
                VALUES (%s, %s, %s, %s, %s)
                """,
                rows,
            )
        conn.commit()
    logger.info(
        f"Inserted {len(records)} attendance records for session id={session_id}"
    )


def get_attendance_history(class_name: str | None = None) -> list[dict]:
    """
    Return past attendance sessions, optionally filtered by class_name.
    Ordered by attendance_date DESC, id DESC.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            if class_name:
                cur.execute(
                    """
                    SELECT id, class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count, created_at
                    FROM attendance_sessions
                    WHERE class_name = %s
                    ORDER BY attendance_date DESC, id DESC
                    """,
                    (class_name,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count, created_at
                    FROM attendance_sessions
                    ORDER BY attendance_date DESC, id DESC
                    """
                )
            rows = cur.fetchall()

    result = []
    for r in rows:
        d = dict(r)
        if hasattr(d.get("attendance_date"), "isoformat"):
            d["attendance_date"] = d["attendance_date"].isoformat()
        if hasattr(d.get("created_at"), "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        result.append(d)
    return result


def get_session_detail(session_id: int) -> dict | None:
    """
    Return full details of an attendance session, including all student records
    joined with student details (name, roll_number).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, class_name, attendance_date, photo_hash, total_faces, recognized_count, unknown_count, created_at
                FROM attendance_sessions
                WHERE id = %s
                """,
                (session_id,),
            )
            session_row = cur.fetchone()
            if not session_row:
                return None

            session_dict = dict(session_row)
            if hasattr(session_dict.get("attendance_date"), "isoformat"):
                session_dict["attendance_date"] = session_dict[
                    "attendance_date"
                ].isoformat()
            if hasattr(session_dict.get("created_at"), "isoformat"):
                session_dict["created_at"] = session_dict["created_at"].isoformat()

            cur.execute(
                """
                SELECT
                    r.id,
                    r.session_id,
                    r.student_id,
                    COALESCE(s.name, 'Deleted Student') AS name,
                    s.roll_number,
                    COALESCE(s.class_name, %s) AS class_name,
                    r.status,
                    r.similarity,
                    r.face_index
                FROM attendance_records r
                LEFT JOIN students s ON r.student_id = s.id
                WHERE r.session_id = %s
                ORDER BY
                    CASE r.status WHEN 'present' THEN 1 ELSE 2 END,
                    s.roll_number ASC,
                    s.name ASC
                """,
                (session_dict["class_name"], session_id),
            )
            record_rows = cur.fetchall()
            session_dict["records"] = [dict(r) for r in record_rows]
            return session_dict


def get_session_by_class_and_date(class_name: str, attendance_date: str) -> dict | None:
    """Return the latest session detail for a given class and date."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT id FROM attendance_sessions
                WHERE class_name = %s AND attendance_date = %s
                ORDER BY id DESC LIMIT 1
                """,
            (class_name, attendance_date),
        )
        row = cur.fetchone()
        if not row:
            return None
        return get_session_detail(row["id"])

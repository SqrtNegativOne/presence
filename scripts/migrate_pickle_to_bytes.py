"""
migrate_pickle_to_bytes.py — One-time migration script to convert pickled
numpy embeddings in presence.db to raw float32 bytes.
"""

import argparse
import pickle
import sqlite3
import sys
from pathlib import Path

import numpy as np


def migrate_database(db_path: Path) -> int:
    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return 0

    print(f"Opening database at {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, roll_number, face_embedding FROM students")
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Error querying students table: {e}")
        conn.close()
        return 0

    migrated_count = 0
    already_bytes_count = 0

    for row in rows:
        student_id = row["id"]
        blob = row["face_embedding"]

        # Check if already 2048 raw bytes
        is_pickle = False
        embedding = None
        try:
            unpickled = pickle.loads(blob)
            if isinstance(unpickled, np.ndarray):
                is_pickle = True
                embedding = unpickled
        except Exception:
            # Not a valid pickle, likely already raw bytes
            pass

        if is_pickle and embedding is not None:
            raw_bytes = embedding.astype(np.float32).tobytes()
            conn.execute(
                "UPDATE students SET face_embedding = ? WHERE id = ?",
                (raw_bytes, student_id),
            )
            migrated_count += 1
            print(
                f"  Migrated student {student_id} ({row['name']}, {row['roll_number']}): "
                f"{len(blob)} bytes -> {len(raw_bytes)} bytes"
            )
        else:
            # Verify it loads with frombuffer
            try:
                arr = np.frombuffer(blob, dtype=np.float32)
                if arr.size in (128, 512):
                    already_bytes_count += 1
                else:
                    print(
                        f"  Warning: student {student_id} embedding has unexpected length {len(blob)} bytes."
                    )
            except Exception as e:
                print(f"  Warning: student {student_id} embedding could not be parsed: {e}")

    conn.commit()
    conn.close()

    print(
        f"Migration complete: {migrated_count} migrated, {already_bytes_count} already in bytes format."
    )
    return migrated_count


def main():
    parser = argparse.ArgumentParser(description="Migrate face embeddings from pickle to raw bytes.")
    default_db = Path(__file__).resolve().parent.parent / "backend" / "data" / "presence.db"
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db,
        help=f"Path to presence.db (default: {default_db})",
    )
    args = parser.parse_args()

    migrate_database(args.db)


if __name__ == "__main__":
    main()

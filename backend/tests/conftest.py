import os
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

import database
from main import app

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://presence:presence@127.0.0.1:5433/presence"),
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Point database to test PostgreSQL instance and ensure tables exist."""
    database.set_database_url(TEST_DB_URL)
    database.init_db()
    yield
    database.close_pool()


@pytest.fixture
def tmp_db():
    """Fixture to provide a clean truncated database for each test."""
    database.set_database_url(TEST_DB_URL)
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE attendance_records, attendance_sessions, students RESTART IDENTITY CASCADE;")
        conn.commit()
    yield
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE attendance_records, attendance_sessions, students RESTART IDENTITY CASCADE;")
        conn.commit()


@pytest.fixture
def client(tmp_db):
    """TestClient using the isolated temporary test database."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def dummy_embedding():
    """Generate a normalized 512-d float32 embedding."""
    vec = np.random.randn(512).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm


@pytest.fixture
def dummy_embedding_128():
    """Generate a normalized 128-d float32 embedding for face-api.js."""
    vec = np.random.randn(128).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec / norm


@pytest.fixture
def dummy_image_bytes():
    """Generate a minimal valid 1x1 PNG image in bytes."""
    import io
    from PIL import Image

    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(buf, format="PNG")
    return buf.getvalue()

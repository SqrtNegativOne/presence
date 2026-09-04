import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

import database
from main import app


@pytest.fixture
def tmp_db(tmp_path):
    """Fixture to provide a clean temporary SQLite database for each test."""
    db_file = tmp_path / "test_presence.db"
    old_db_path = database.DB_PATH
    database.DB_PATH = db_file
    database.init_db()
    try:
        yield db_file
    finally:
        database.DB_PATH = old_db_path


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
def dummy_image_bytes():
    """Generate a minimal valid 1x1 PNG image in bytes."""
    import io
    from PIL import Image

    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(buf, format="PNG")
    return buf.getvalue()

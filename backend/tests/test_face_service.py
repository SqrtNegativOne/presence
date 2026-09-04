from unittest.mock import MagicMock, patch

import numpy as np

from services.face_service import THRESHOLD, match_group_photo


class MockFace:
    def __init__(self, embedding, bbox=None):
        self.embedding = embedding
        self.bbox = bbox or [10, 20, 100, 120]


def test_matching_above_threshold():
    # Construct base unit vector
    base_vec = np.zeros(512, dtype=np.float32)
    base_vec[0] = 1.0

    # Target vector with similarity ~0.41
    # sim = cos(theta) -> dot product = 0.41
    target_vec = np.zeros(512, dtype=np.float32)
    target_vec[0] = 0.41
    target_vec[1] = np.sqrt(1 - 0.41**2).astype(np.float32)

    known_students = [
        {
            "id": 1,
            "name": "Alice",
            "roll_number": "CS101",
            "class_name": "10-A",
            "face_embedding": base_vec,
        }
    ]

    mock_app = MagicMock()
    mock_app.get.return_value = [MockFace(target_vec)]

    with (
        patch("services.face_service.get_face_app", return_value=mock_app),
        patch(
            "services.face_service._bytes_to_bgr",
            return_value=np.zeros((100, 100, 3), dtype=np.uint8),
        ),
    ):
        results = match_group_photo(b"dummy_bytes", known_students)

    assert len(results) == 1
    assert results[0]["status"] == "recognized"
    assert results[0]["student_id"] == 1
    assert results[0]["name"] == "Alice"
    assert results[0]["similarity"] >= THRESHOLD


def test_matching_below_threshold():
    # Construct base unit vector
    base_vec = np.zeros(512, dtype=np.float32)
    base_vec[0] = 1.0

    # Target vector with similarity ~0.39 (< 0.40 threshold)
    target_vec = np.zeros(512, dtype=np.float32)
    target_vec[0] = 0.39
    target_vec[1] = np.sqrt(1 - 0.39**2).astype(np.float32)

    known_students = [
        {
            "id": 1,
            "name": "Alice",
            "roll_number": "CS101",
            "class_name": "10-A",
            "face_embedding": base_vec,
        }
    ]

    mock_app = MagicMock()
    mock_app.get.return_value = [MockFace(target_vec)]

    with (
        patch("services.face_service.get_face_app", return_value=mock_app),
        patch(
            "services.face_service._bytes_to_bgr",
            return_value=np.zeros((100, 100, 3), dtype=np.uint8),
        ),
    ):
        results = match_group_photo(b"dummy_bytes", known_students)

    assert len(results) == 1
    assert results[0]["status"] == "unknown"
    assert results[0]["student_id"] is None
    assert results[0]["name"] == "Unknown"
    assert results[0]["similarity"] < THRESHOLD


def test_matching_no_duplicate_assignments():
    # If two faces both match Alice, only the best match should get Alice, the second should be Unknown
    base_vec = np.zeros(512, dtype=np.float32)
    base_vec[0] = 1.0

    face1_vec = np.zeros(512, dtype=np.float32)
    face1_vec[0] = 0.9  # very close match
    face1_vec[1] = np.sqrt(1 - 0.9**2).astype(np.float32)

    face2_vec = np.zeros(512, dtype=np.float32)
    face2_vec[0] = 0.7  # also above threshold, but Alice already taken
    face2_vec[1] = np.sqrt(1 - 0.7**2).astype(np.float32)

    known_students = [
        {
            "id": 1,
            "name": "Alice",
            "roll_number": "CS101",
            "class_name": "10-A",
            "face_embedding": base_vec,
        }
    ]

    mock_app = MagicMock()
    mock_app.get.return_value = [MockFace(face1_vec), MockFace(face2_vec)]

    with (
        patch("services.face_service.get_face_app", return_value=mock_app),
        patch(
            "services.face_service._bytes_to_bgr",
            return_value=np.zeros((100, 100, 3), dtype=np.uint8),
        ),
    ):
        results = match_group_photo(b"dummy_bytes", known_students)

    assert len(results) == 2
    assert results[0]["status"] == "recognized"
    assert results[0]["student_id"] == 1
    assert results[1]["status"] == "unknown"
    assert results[1]["student_id"] is None

"""
Tests for the pure-numpy matcher in services/matching.py.

These run in every environment (lite or cloud) because the module has no heavy
ML dependencies.
"""

import numpy as np

from services.matching import THRESHOLD, match_embeddings


def _unit(vec: np.ndarray) -> np.ndarray:
    return (vec / np.linalg.norm(vec)).astype(np.float32)


def _student(student_id: int, embedding: np.ndarray) -> dict:
    return {
        "id": student_id,
        "name": f"Student {student_id}",
        "roll_number": f"CS{student_id}",
        "class_name": "10-A",
        "face_embedding": embedding,
    }


def _vec_with_similarity(dim: int, similarity: float) -> np.ndarray:
    """Return a unit vector whose dot product with e0 is `similarity`."""
    v = np.zeros(dim, dtype=np.float32)
    v[0] = similarity
    v[1] = np.sqrt(max(0.0, 1 - similarity**2)).astype(np.float32)
    return v


def test_recognizes_above_local_threshold():
    base = np.zeros(128, dtype=np.float32)
    base[0] = 1.0
    query = _vec_with_similarity(128, 0.95)

    results = match_embeddings([query], [_student(1, base)])

    assert len(results) == 1
    assert results[0]["status"] == "recognized"
    assert results[0]["student_id"] == 1
    assert results[0]["similarity"] >= 0.6


def test_unknown_below_local_threshold():
    base = np.zeros(128, dtype=np.float32)
    base[0] = 1.0
    query = _vec_with_similarity(128, 0.5)  # < 0.6 local threshold

    results = match_embeddings([query], [_student(1, base)])

    assert results[0]["status"] == "unknown"
    assert results[0]["student_id"] is None
    assert results[0]["name"] == "Unknown"


def test_cloud_threshold_used_for_512_d():
    base = np.zeros(512, dtype=np.float32)
    base[0] = 1.0
    query = _vec_with_similarity(512, 0.5)  # > 0.4 cloud threshold

    results = match_embeddings([query], [_student(1, base)])

    assert results[0]["status"] == "recognized"
    assert results[0]["similarity"] >= THRESHOLD


def test_no_duplicate_student_assignments():
    base = np.zeros(128, dtype=np.float32)
    base[0] = 1.0

    results = match_embeddings(
        [_vec_with_similarity(128, 0.99), _vec_with_similarity(128, 0.9)],
        [_student(1, base)],
    )

    assert results[0]["status"] == "recognized"
    assert results[0]["student_id"] == 1
    assert results[1]["status"] == "unknown"
    assert results[1]["student_id"] is None


def test_mixed_embedding_dimensions_are_isolated():
    """A 512-d enrolled student must never be matched against a 128-d query."""
    base_512 = np.zeros(512, dtype=np.float32)
    base_512[0] = 1.0
    query_128 = _vec_with_similarity(128, 1.0)

    results = match_embeddings([query_128], [_student(1, base_512)])

    assert results[0]["status"] == "unknown"
    assert results[0]["student_id"] is None


def test_explicit_threshold_override():
    base = np.zeros(128, dtype=np.float32)
    base[0] = 1.0
    query = _vec_with_similarity(128, 0.7)

    results = match_embeddings([query], [_student(1, base)], threshold=0.9)

    assert results[0]["status"] == "unknown"


def test_empty_queries_returns_empty_list():
    assert match_embeddings([], [_student(1, np.zeros(128, dtype=np.float32))]) == []


def test_bboxes_are_attached_to_results():
    base = np.zeros(128, dtype=np.float32)
    base[0] = 1.0
    query = _vec_with_similarity(128, 0.99)

    results = match_embeddings([query], [_student(1, base)], bboxes=[[1, 2, 3, 4]])

    assert results[0]["bbox"] == [1, 2, 3, 4]

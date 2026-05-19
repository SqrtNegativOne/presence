"""
face_service.py — orchestrates a chosen recognizer + a per-user embedding cache.

What changed vs. the original single-engine version:
- The recognizer is pluggable (see recognizers/). Each call picks one by name.
- Matching is fully vectorized: every embedding is L2-normalized at ingest, so
  cosine similarity collapses to a single (N×D) · (D×M) matmul. For a class of
  30 with 20 faces in the photo, that's ~600 Python-level ops replaced by one
  BLAS call.
- A per-(user_id, recognizer_name) cache holds the pre-stacked (M, D) student
  matrix plus parallel metadata, so the hot path no longer reads from SQLite
  or unpickles per request. Mutations invalidate the affected cache entry.
"""
from __future__ import annotations

import threading
from typing import Optional

import cv2
import numpy as np
from loguru import logger

import database
from recognizers import (
    DetectedFace,
    FaceRecognizer,
    default_name,
    get_recognizer,
    list_available,
)


# ---------------------------------------------------------------------------
# Embedding cache: { (user_id, recognizer_name): _CachedStudents }
# ---------------------------------------------------------------------------
class _CachedStudents:
    __slots__ = ("matrix", "meta")

    def __init__(self, matrix: np.ndarray, meta: list[dict]) -> None:
        self.matrix = matrix     # shape (M, D), float32, rows L2-normalized
        self.meta = meta         # parallel list: [{id, name, roll_number, class_name}, ...]


_cache: dict[tuple[int, str], _CachedStudents] = {}
_cache_lock = threading.Lock()


def invalidate_cache(user_id: Optional[int] = None, recognizer_name: Optional[str] = None) -> None:
    """Drop cached student matrices. Call after enroll/delete.

    With no args, drops everything. With just user_id, drops all recognizers
    for that user. With both, drops the precise (user, recognizer) entry.
    """
    with _cache_lock:
        if user_id is None:
            _cache.clear()
            return
        for key in [k for k in _cache if k[0] == user_id
                    and (recognizer_name is None or k[1] == recognizer_name)]:
            _cache.pop(key, None)


def _load_cache(user_id: int, recognizer_name: str) -> _CachedStudents:
    key = (user_id, recognizer_name)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached

    rows = database.get_user_students_with_embeddings(user_id, recognizer_name)
    if rows:
        matrix = np.vstack([r["face_embedding"] for r in rows]).astype(np.float32, copy=False)
        # Re-assert L2 normalization defensively (older rows might not be normalized)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms
    else:
        matrix = np.zeros((0, 0), dtype=np.float32)
    meta = [{"id": r["id"], "name": r["name"],
             "roll_number": r["roll_number"], "class_name": r["class_name"]}
            for r in rows]

    cached = _CachedStudents(matrix, meta)
    with _cache_lock:
        _cache[key] = cached
    return cached


# ---------------------------------------------------------------------------
# Image decode helper
# ---------------------------------------------------------------------------
def _bytes_to_bgr(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Make sure it is a valid JPEG or PNG.")
    return img


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def available_recognizers() -> list[dict]:
    return list_available()


def encode_single_face(image_bytes: bytes, recognizer_name: str) -> tuple[np.ndarray, str]:
    """Detect exactly one face in a portrait. Returns (embedding, recognizer_name).

    Embedding is L2-normalized float32.
    """
    rec: FaceRecognizer = get_recognizer(recognizer_name)
    img_bgr = _bytes_to_bgr(image_bytes)
    faces = rec.detect_and_encode(img_bgr)
    if len(faces) == 0:
        raise ValueError(
            "No face detected in the enrollment photo. "
            "Please use a clear, well-lit photo with the student's face visible."
        )
    if len(faces) > 1:
        raise ValueError(
            f"{len(faces)} faces detected. Enrollment photos must contain exactly one person."
        )
    return faces[0].embedding.astype(np.float32, copy=False), recognizer_name


def match_group_photo(
    image_bytes: bytes,
    user_id: int,
    recognizer_name: str,
) -> list[dict]:
    """Detect every face in a photo and match it against the user's enrolled students.

    Uses a single BLAS matmul over the cached embedding matrix.
    """
    rec: FaceRecognizer = get_recognizer(recognizer_name)
    img_bgr = _bytes_to_bgr(image_bytes)
    faces: list[DetectedFace] = rec.detect_and_encode(img_bgr)
    logger.info(f"[{recognizer_name}] detected {len(faces)} faces")

    cached = _load_cache(user_id, recognizer_name)
    threshold = rec.threshold

    if cached.matrix.shape[0] == 0 or len(faces) == 0:
        # Nothing to match against, or no faces — emit "unknown" results
        return [_unknown_result(i, f) for i, f in enumerate(faces)]

    # Stack query embeddings: shape (N, D). Both sides already L2-normalized.
    query = np.vstack([f.embedding for f in faces]).astype(np.float32, copy=False)
    # Defensive normalize (no-op for ArcFace, cheap)
    q_norm = np.linalg.norm(query, axis=1, keepdims=True)
    q_norm[q_norm == 0] = 1.0
    query = query / q_norm

    # Single matmul: (N, D) @ (D, M) -> (N, M) cosine similarity matrix.
    sims = query @ cached.matrix.T
    best_idx = sims.argmax(axis=1)
    best_sim = sims[np.arange(len(faces)), best_idx]

    results: list[dict] = []
    for i, face in enumerate(faces):
        sim = float(best_sim[i])
        if sim >= threshold:
            m = cached.meta[int(best_idx[i])]
            results.append({
                "face_index": i + 1,
                "bbox": list(face.bbox),
                "name": m["name"],
                "roll_number": m["roll_number"],
                "class_name": m["class_name"],
                "status": "recognized",
                "similarity": round(sim, 4),
            })
        else:
            results.append(_unknown_result(i, face, sim))
    return results


def _unknown_result(i: int, face: DetectedFace, sim: float = -1.0) -> dict:
    return {
        "face_index": i + 1,
        "bbox": list(face.bbox),
        "name": "Unknown",
        "roll_number": None,
        "class_name": None,
        "status": "unknown",
        "similarity": round(sim, 4),
    }

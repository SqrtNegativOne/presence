"""
matching.py — Pure-numpy embedding matching.

This module is intentionally free of any heavy ML runtime (no InsightFace,
ONNX Runtime, OpenCV, or Pillow). That keeps local-only deployments light:
the browser computes embeddings and the backend only needs numpy + stdlib
to match them against what is stored in PostgreSQL.

Cloud inference lives in services/face_service.py, which imports the matcher
from here.
"""

from collections.abc import Sequence

import numpy as np
from loguru import logger

# Cosine similarity threshold. Tuned for ArcFace 512-d embeddings.
# Higher value = stricter match (fewer false positives, more unknowns).
THRESHOLD = 0.4


def match_embeddings(
    query_embeddings: list[np.ndarray],
    known_students: list[dict],
    threshold: float | None = None,
    bboxes: Sequence[Sequence[int] | None] | None = None,
) -> list[dict]:
    """
    Match a list of raw face embeddings against known students using cosine similarity.

    Args:
        query_embeddings: list of 1D numpy float32 arrays (e.g. 128-d or 512-d)
        known_students: list of dicts with keys: id, name, roll_number, class_name, face_embedding (numpy array)
        threshold: cosine similarity threshold (default: 0.6 for <=128-d, THRESHOLD for >128-d)
        bboxes: optional list of [x1, y1, x2, y2] bounding boxes matching query_embeddings

    Returns:
        List of dicts, one per query embedding:
            {
              "face_index":  int,
              "bbox":        [x1, y1, x2, y2] | None,
              "student_id":  int | None,
              "name":        str,
              "roll_number": str | None,
              "class_name":  str | None,
              "status":      "recognized" | "unknown",
              "similarity":  float,
            }
    """
    results = []
    if not query_embeddings:
        return results

    # Normalize query embeddings and ensure float32 arrays
    norm_queries = []
    for q in query_embeddings:
        arr = np.asarray(q, dtype=np.float32)
        norm = np.linalg.norm(arr)
        norm_queries.append(arr / norm if norm > 0 else arr)

    dim = len(norm_queries[0])
    # Filter known students to only those with matching embedding dimension
    matching_students = [
        s
        for s in known_students
        if isinstance(s.get("face_embedding"), np.ndarray)
        and len(s["face_embedding"]) == dim
    ]

    effective_threshold = threshold
    if effective_threshold is None:
        effective_threshold = 0.6 if dim <= 128 else THRESHOLD

    known_embeddings = None
    if matching_students:
        known_normed = []
        for s in matching_students:
            emb = s["face_embedding"]
            norm = np.linalg.norm(emb)
            known_normed.append(emb / norm if norm > 0 else emb)
        known_embeddings = np.array(known_normed, dtype=np.float32)

    matched_student_ids = set()

    for i, query_embedding in enumerate(norm_queries):
        bbox = bboxes[i] if bboxes and i < len(bboxes) else None

        best_match = None
        best_similarity = -1.0
        max_sim_for_face = 0.0

        if known_embeddings is not None and len(known_embeddings) > 0:
            similarities = np.dot(known_embeddings, query_embedding)
            max_sim_for_face = float(np.max(similarities))

            sorted_indices = np.argsort(similarities)[::-1]
            for idx in sorted_indices:
                sim = float(similarities[idx])
                if sim < effective_threshold:
                    break

                student = matching_students[idx]
                if student["id"] not in matched_student_ids:
                    best_match = student
                    best_similarity = sim
                    break

        if best_match is not None:
            matched_student_ids.add(best_match["id"])
            results.append(
                {
                    "face_index": i + 1,
                    "bbox": bbox,
                    "student_id": best_match["id"],
                    "name": best_match["name"],
                    "roll_number": best_match["roll_number"],
                    "class_name": best_match["class_name"],
                    "status": "recognized",
                    "similarity": round(best_similarity, 4),
                }
            )
            logger.debug(
                f"Face {i + 1}: {best_match['name']} (similarity={best_similarity:.4f})"
            )
        else:
            results.append(
                {
                    "face_index": i + 1,
                    "bbox": bbox,
                    "student_id": None,
                    "name": "Unknown",
                    "roll_number": None,
                    "class_name": None,
                    "status": "unknown",
                    "similarity": round(max_sim_for_face, 4),
                }
            )
            logger.debug(f"Face {i + 1}: Unknown")

    return results

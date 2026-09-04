"""
face_service.py — All face recognition logic using InsightFace (ArcFace / buffalo_l).

KEY CONCEPTS:
- FaceAnalysis is a pipeline: it detects faces in an image AND computes a 512-d
  "embedding" (a vector of numbers) for each face.
- Two faces of the same person produce similar embeddings; different people produce
  different embeddings. We measure similarity with cosine similarity (0.0–1.0).
- Threshold 0.4: if similarity > 0.4, we consider it the same person.
  ArcFace embeddings are L2-normalised, so cosine similarity is equivalent to dot product.
"""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger

# InsightFace's main class — handles detection + recognition in one shot.
from insightface.app import FaceAnalysis

# We cache the model in our own data/ folder so it's project-local.
MODEL_CACHE_DIR = str(Path(__file__).parent.parent / "data")

# Cosine similarity threshold. Tuned for ArcFace 512-d embeddings.
# Higher value = stricter match (fewer false positives, more unknowns).
THRESHOLD = 0.4

# ---------------------------------------------------------------------------
# Singleton: load the model exactly once when this module is first imported.
# Loading takes ~5s and uses ~500 MB of disk. We don't want to do it per request.
# ---------------------------------------------------------------------------
_face_app: Optional[FaceAnalysis] = None


def get_face_app() -> FaceAnalysis:
    """
    Return the shared FaceAnalysis instance, creating it on first call.
    On first run ever, InsightFace downloads buffalo_l (~500 MB) to ~/.insightface/.
    Subsequent runs load from the local cache in seconds.
    """
    global _face_app
    if _face_app is None:
        logger.info("Loading InsightFace buffalo_l model (first run may download ~500 MB)…")
        _face_app = FaceAnalysis(
            name="buffalo_l",
            root=MODEL_CACHE_DIR,          # cache models here instead of ~/.insightface
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],  # try GPU, fall back to CPU
        )
        # det_size: the resolution InsightFace internally resizes to before detection.
        # 640×640 gives a good balance of speed and accuracy for group photos.
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
        logger.success("InsightFace model loaded.")
    return _face_app


# ---------------------------------------------------------------------------
# Helper: bytes → numpy image (BGR, which OpenCV and InsightFace expect)
# ---------------------------------------------------------------------------

def _bytes_to_bgr(image_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes (JPEG/PNG/etc.) into a numpy BGR array."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)  # result is BGR
    if img is None:
        raise ValueError("Could not decode image. Make sure it is a valid JPEG or PNG.")
    return img


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode_single_face(image_bytes: bytes) -> np.ndarray:
    """
    Given a solo-portrait image (bytes), detect exactly one face and return its
    512-d float32 embedding.

    Raises ValueError if 0 or >1 faces are found — enrollment must be solo.
    """
    app = get_face_app()
    img_bgr = _bytes_to_bgr(image_bytes)
    faces = app.get(img_bgr)  # list of Face objects

    if len(faces) == 0:
        raise ValueError(
            "No face detected in the enrollment photo. "
            "Please use a clear, well-lit photo with the student's face visible."
        )
    if len(faces) > 1:
        raise ValueError(
            f"{len(faces)} faces detected. Enrollment photos must contain exactly one person."
        )

    embedding = faces[0].embedding  # shape (512,), dtype float32
    logger.debug(f"Encoded single face, embedding norm={np.linalg.norm(embedding):.4f}")
    return embedding


def match_embeddings(
    query_embeddings: list[np.ndarray],
    known_students: list[dict],
    threshold: Optional[float] = None,
    bboxes: Optional[list[Optional[list[int]]]] = None,
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
        s for s in known_students
        if isinstance(s.get("face_embedding"), np.ndarray) and len(s["face_embedding"]) == dim
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
            results.append({
                "face_index": i + 1,
                "bbox": bbox,
                "student_id": best_match["id"],
                "name": best_match["name"],
                "roll_number": best_match["roll_number"],
                "class_name": best_match["class_name"],
                "status": "recognized",
                "similarity": round(best_similarity, 4),
            })
            logger.debug(f"Face {i+1}: {best_match['name']} (similarity={best_similarity:.4f})")
        else:
            results.append({
                "face_index": i + 1,
                "bbox": bbox,
                "student_id": None,
                "name": "Unknown",
                "roll_number": None,
                "class_name": None,
                "status": "unknown",
                "similarity": round(max_sim_for_face, 4),
            })
            logger.debug(f"Face {i+1}: Unknown")

    return results


def match_group_photo(image_bytes: bytes, known_students: list[dict]) -> list[dict]:
    """
    Detect all faces in a group photo and match each to the known students.
    """
    app = get_face_app()
    img_bgr = _bytes_to_bgr(image_bytes)
    faces = app.get(img_bgr)

    logger.info(f"Detected {len(faces)} faces in group photo")
    query_embeddings = [face.embedding for face in faces]
    bboxes = [[int(v) for v in face.bbox] for face in faces]

    return match_embeddings(
        query_embeddings=query_embeddings,
        known_students=known_students,
        threshold=THRESHOLD,
        bboxes=bboxes,
    )


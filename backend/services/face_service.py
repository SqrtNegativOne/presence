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


def match_group_photo(image_bytes: bytes, known_students: list[dict]) -> list[dict]:
    """
    Detect all faces in a group photo and match each to the known students.

    Args:
        image_bytes: raw bytes of the group photo
        known_students: list of dicts with keys: id, name, roll_number, class_name, face_embedding (numpy array)

    Returns:
        List of dicts, one per detected face:
            {
              "face_index":  int,        # 1-based display index
              "bbox":        [x1,y1,x2,y2],  # pixel coords for annotation
              "name":        str,         # student name or "Unknown"
              "roll_number": str | None,
              "class_name":  str | None,
              "status":      "recognized" | "unknown",
              "similarity":  float,       # best cosine similarity found
            }
    """
    app = get_face_app()
    img_bgr = _bytes_to_bgr(image_bytes)
    faces = app.get(img_bgr)

    logger.info(f"Detected {len(faces)} faces in group photo")
    results = []

    # Pre-compute matrix of all known embeddings for fast vectorized operations
    if known_students:
        known_embeddings = np.array([s["face_embedding"] for s in known_students])
    
    matched_student_ids = set()

    for i, face in enumerate(faces):
        bbox = [int(v) for v in face.bbox]  # [x1, y1, x2, y2]
        query_embedding = face.embedding     # 512-d float32

        best_match = None
        best_similarity = -1.0
        max_sim_for_face = 0.0
        
        if known_students:
            # Compute similarity of this face against ALL known students in a single vectorized operation
            # ArcFace embeddings are L2-normalised, so dot product equals cosine similarity
            similarities = np.dot(known_embeddings, query_embedding)
            max_sim_for_face = float(np.max(similarities))
            
            # Sort indices by similarity descending
            sorted_indices = np.argsort(similarities)[::-1]
            
            for idx in sorted_indices:
                sim = similarities[idx]
                if sim < THRESHOLD:
                    break  # Remaining matches are even lower, stop checking
                
                student = known_students[idx]
                if student["id"] not in matched_student_ids:
                    best_match = student
                    best_similarity = float(sim)
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

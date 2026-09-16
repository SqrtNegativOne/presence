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

import cv2
import numpy as np

# InsightFace's main class — handles detection + recognition in one shot.
from insightface.app import FaceAnalysis
from loguru import logger

# Re-exported for backwards compatibility. The pure matcher lives in
# services/matching.py so local-only deployments never import the heavy
# InsightFace / OpenCV stack just to match browser-computed embeddings.
from services.matching import THRESHOLD, match_embeddings

__all__ = ["THRESHOLD", "match_embeddings", "encode_single_face", "match_group_photo"]

# We cache the model in our own data/ folder so it's project-local.
MODEL_CACHE_DIR = str(Path(__file__).parent.parent / "data")

# ---------------------------------------------------------------------------
# Singleton: load the model exactly once when this module is first imported.
# Loading takes ~5s and uses ~500 MB of disk. We don't want to do it per request.
# ---------------------------------------------------------------------------
_face_app: FaceAnalysis | None = None


def get_face_app() -> FaceAnalysis:
    """
    Return the shared FaceAnalysis instance, creating it on first call.
    On first run ever, InsightFace downloads buffalo_l (~500 MB) to ~/.insightface/.
    Subsequent runs load from the local cache in seconds.
    """
    global _face_app
    if _face_app is None:
        logger.info(
            "Loading InsightFace buffalo_l model (first run may download ~500 MB)…"
        )
        _face_app = FaceAnalysis(
            name="buffalo_l",
            root=MODEL_CACHE_DIR,  # cache models here instead of ~/.insightface
            providers=[
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ],  # try GPU, fall back to CPU
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

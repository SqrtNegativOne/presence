"""
OpenCV Haar-cascade recognizer.

Detection: classical Viola-Jones Haar cascade — runs in milliseconds on CPU
with no deep-learning weights. Recognition: each detected face is cropped to
64×64 grayscale, histogram-equalized, flattened, and L2-normalized. The result
is a 4096-d "embedding" that has no semantic meaning but is reproducible.

Accuracy is much lower than ArcFace — this is included as the "fastest"
baseline for benchmarking and for environments where InsightFace can't run.
"""
from __future__ import annotations

import cv2
import numpy as np

from .base import DetectedFace, FaceRecognizer


def _embed_crop(face_gray: np.ndarray, size: int = 64) -> np.ndarray:
    resized = cv2.resize(face_gray, (size, size), interpolation=cv2.INTER_AREA)
    eq = cv2.equalizeHist(resized)
    vec = eq.astype(np.float32).ravel()
    n = np.linalg.norm(vec)
    if n > 0:
        vec /= n
    return vec


class OpenCVHaar(FaceRecognizer):
    name = "opencv_haar"
    display_name = "OpenCV · Haar + Pixel"
    description = "Classical Haar detection + pixel embedding. Very fast, low accuracy."
    embedding_dim = 64 * 64
    threshold = 0.85   # cosine on flattened pixels is much higher than ArcFace
    speed = "fastest"

    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError(f"Could not load Haar cascade at {cascade_path}")

    def detect_and_encode(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        boxes = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(40, 40),
        )
        out: list[DetectedFace] = []
        for (x, y, w, h) in boxes:
            x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)
            face_gray = gray[y1:y2, x1:x2]
            if face_gray.size == 0:
                continue
            out.append(DetectedFace(
                bbox=(x1, y1, x2, y2),
                embedding=_embed_crop(face_gray),
                det_score=1.0,
            ))
        return out

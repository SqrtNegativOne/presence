"""
MediaPipe BlazeFace recognizer.

Google's BlazeFace is the detector that ships with MediaPipe — designed for
real-time mobile use, it's the fastest detector in this app on CPU. Recognition
uses the same crude pixel embedding as the Haar recognizer (so it's a peer
"fast baseline", not a serious face-ID engine).

The mediapipe import is deferred to construction time so import-time failure
(unsupported platform, missing wheel) only disables this recognizer instead of
crashing the whole backend.
"""
from __future__ import annotations

import cv2
import numpy as np

from .base import DetectedFace, FaceRecognizer
from .opencv_haar import _embed_crop


class MediaPipeBlaze(FaceRecognizer):
    name = "mediapipe_blaze"
    display_name = "MediaPipe · BlazeFace + Pixel"
    description = "BlazeFace detector + pixel embedding. Fastest detection, low recognition accuracy."
    embedding_dim = 64 * 64
    threshold = 0.85
    speed = "fastest"

    def __init__(self) -> None:
        import mediapipe as mp  # local import, may be missing
        self._mp_fd = mp.solutions.face_detection
        # model_selection=1 covers faces up to ~5 m; better for group photos
        self._detector = self._mp_fd.FaceDetection(
            model_selection=1, min_detection_confidence=0.5
        )

    def detect_and_encode(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        h, w = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        results = self._detector.process(rgb)
        out: list[DetectedFace] = []
        if not results.detections:
            return out
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        for det in results.detections:
            r = det.location_data.relative_bounding_box
            x1 = max(0, int(r.xmin * w))
            y1 = max(0, int(r.ymin * h))
            x2 = min(w, int((r.xmin + r.width) * w))
            y2 = min(h, int((r.ymin + r.height) * h))
            if x2 <= x1 or y2 <= y1:
                continue
            face_gray = gray[y1:y2, x1:x2]
            if face_gray.size == 0:
                continue
            out.append(DetectedFace(
                bbox=(x1, y1, x2, y2),
                embedding=_embed_crop(face_gray),
                det_score=float(det.score[0]) if det.score else 1.0,
            ))
        return out

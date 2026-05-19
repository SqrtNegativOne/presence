"""
InsightFace recognizers — buffalo_l (accurate), buffalo_s (faster), buffalo_sc (fastest).

All three are 512-d ArcFace variants. The smaller packs use a smaller detector
(SCRFD-500MF vs SCRFD-10GF) and a smaller recognition backbone, so they are
several times faster on CPU at a small accuracy cost.

InsightFace already L2-normalizes its embeddings, so we re-assert that invariant
in detect_and_encode rather than re-normalizing.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from loguru import logger

from .base import DetectedFace, FaceRecognizer

_MODEL_CACHE_DIR = str(Path(__file__).parent.parent / "data")


class _InsightFaceRecognizer(FaceRecognizer):
    embedding_dim = 512

    def __init__(self, model_pack: str, det_size: tuple[int, int]) -> None:
        self._model_pack = model_pack
        self._det_size = det_size
        self._app = None  # lazy

    def warm_up(self) -> None:
        if self._app is not None:
            return
        from insightface.app import FaceAnalysis  # heavy import — keep local
        logger.info(f"Loading InsightFace pack '{self._model_pack}' (det_size={self._det_size})…")
        app = FaceAnalysis(
            name=self._model_pack,
            root=_MODEL_CACHE_DIR,
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=0, det_size=self._det_size)
        self._app = app
        logger.success(f"InsightFace '{self._model_pack}' ready.")

    def detect_and_encode(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        self.warm_up()
        faces = self._app.get(image_bgr)
        out: list[DetectedFace] = []
        for f in faces:
            x1, y1, x2, y2 = (int(v) for v in f.bbox)
            emb = np.asarray(f.embedding, dtype=np.float32)
            n = np.linalg.norm(emb)
            if n > 0:
                emb = emb / n
            out.append(DetectedFace(
                bbox=(x1, y1, x2, y2),
                embedding=emb,
                det_score=float(getattr(f, "det_score", 1.0)),
            ))
        return out


class InsightFaceLarge(_InsightFaceRecognizer):
    name = "insightface_l"
    display_name = "InsightFace · buffalo_l"
    description = "ArcFace large model. Best accuracy, ~500 MB, slower."
    threshold = 0.40
    speed = "accurate"

    def __init__(self) -> None:
        super().__init__("buffalo_l", det_size=(640, 640))


class InsightFaceSmall(_InsightFaceRecognizer):
    name = "insightface_s"
    display_name = "InsightFace · buffalo_s"
    description = "ArcFace small model. 2-3x faster, slight accuracy drop."
    threshold = 0.38
    speed = "balanced"

    def __init__(self) -> None:
        super().__init__("buffalo_s", det_size=(640, 640))


class InsightFaceSmallCompact(_InsightFaceRecognizer):
    name = "insightface_sc"
    display_name = "InsightFace · buffalo_sc"
    description = "Smallest InsightFace pack. ~5x faster, noticeable accuracy drop."
    threshold = 0.35
    speed = "fast"

    def __init__(self) -> None:
        # Smaller detector size pairs well with the smaller backbone
        super().__init__("buffalo_sc", det_size=(480, 480))

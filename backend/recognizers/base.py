"""
Base types every face-recognition backend implements.

Embeddings are float32 numpy arrays, ALWAYS L2-normalized. That invariant lets
the matcher in services/face_service.py compute cosine similarity with a single
matmul (no per-pair `np.linalg.norm` calls).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class DetectedFace:
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2 in pixel coords
    embedding: np.ndarray             # shape (embedding_dim,), float32, L2-normalized
    det_score: float = 1.0            # detector confidence in [0, 1]


class FaceRecognizer(ABC):
    """Abstract recognizer. Subclasses are singletons created by the registry."""

    name: str             # stable id used in the DB (e.g. "insightface_l")
    display_name: str     # shown in the UI
    description: str      # one-line summary
    embedding_dim: int    # dimensionality of the embeddings produced
    threshold: float      # default cosine-similarity threshold for a match
    speed: str            # "fastest" | "fast" | "balanced" | "accurate"

    @abstractmethod
    def detect_and_encode(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        """Detect every face and return one DetectedFace per face."""

    def warm_up(self) -> None:
        """Optional hook to load weights eagerly."""
        return None

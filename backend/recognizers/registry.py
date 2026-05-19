"""
Registry of available face recognizers.

Each recognizer is instantiated at most once (singletons, lazy). Construction is
wrapped in try/except so a missing optional dependency (e.g. mediapipe) just
hides that one engine from the listing — the others keep working.
"""
from __future__ import annotations

from typing import Callable

from loguru import logger

from .base import FaceRecognizer
from .insightface_engine import (
    InsightFaceLarge,
    InsightFaceSmall,
    InsightFaceSmallCompact,
)
from .opencv_haar import OpenCVHaar
from .mediapipe_blaze import MediaPipeBlaze

# (factory, advertised metadata) — metadata is duplicated here so listing
# available recognizers doesn't require instantiating them (which can be heavy).
_FACTORIES: dict[str, Callable[[], FaceRecognizer]] = {
    "insightface_l":  InsightFaceLarge,
    "insightface_s":  InsightFaceSmall,
    "insightface_sc": InsightFaceSmallCompact,
    "opencv_haar":    OpenCVHaar,
    "mediapipe_blaze": MediaPipeBlaze,
}

_META: dict[str, dict] = {
    "insightface_l":   {"display_name": InsightFaceLarge.display_name,
                        "description": InsightFaceLarge.description,
                        "embedding_dim": InsightFaceLarge.embedding_dim,
                        "threshold": InsightFaceLarge.threshold,
                        "speed": InsightFaceLarge.speed},
    "insightface_s":   {"display_name": InsightFaceSmall.display_name,
                        "description": InsightFaceSmall.description,
                        "embedding_dim": InsightFaceSmall.embedding_dim,
                        "threshold": InsightFaceSmall.threshold,
                        "speed": InsightFaceSmall.speed},
    "insightface_sc":  {"display_name": InsightFaceSmallCompact.display_name,
                        "description": InsightFaceSmallCompact.description,
                        "embedding_dim": InsightFaceSmallCompact.embedding_dim,
                        "threshold": InsightFaceSmallCompact.threshold,
                        "speed": InsightFaceSmallCompact.speed},
    "opencv_haar":     {"display_name": OpenCVHaar.display_name,
                        "description": OpenCVHaar.description,
                        "embedding_dim": OpenCVHaar.embedding_dim,
                        "threshold": OpenCVHaar.threshold,
                        "speed": OpenCVHaar.speed},
    "mediapipe_blaze": {"display_name": MediaPipeBlaze.display_name,
                        "description": MediaPipeBlaze.description,
                        "embedding_dim": MediaPipeBlaze.embedding_dim,
                        "threshold": MediaPipeBlaze.threshold,
                        "speed": MediaPipeBlaze.speed},
}

_INSTANCES: dict[str, FaceRecognizer] = {}
_UNAVAILABLE: dict[str, str] = {}  # name -> reason


def default_name() -> str:
    return "insightface_l"


def get_recognizer(name: str) -> FaceRecognizer:
    """Return the singleton recognizer with this name. Raises if unknown/unavailable."""
    if name in _INSTANCES:
        return _INSTANCES[name]
    if name in _UNAVAILABLE:
        raise RuntimeError(f"Recognizer '{name}' is unavailable: {_UNAVAILABLE[name]}")
    factory = _FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"Unknown recognizer '{name}'. Known: {list(_FACTORIES)}")
    try:
        inst = factory()
    except Exception as e:
        _UNAVAILABLE[name] = str(e)
        logger.warning(f"Recognizer '{name}' could not be loaded: {e}")
        raise RuntimeError(f"Recognizer '{name}' is unavailable: {e}") from e
    _INSTANCES[name] = inst
    return inst


def list_available() -> list[dict]:
    """Return a list of {name, display_name, description, embedding_dim, speed, available} dicts."""
    out: list[dict] = []
    for name, meta in _META.items():
        available = name not in _UNAVAILABLE
        out.append({"name": name, "available": available, **meta})
    return out


def mark_unavailable(name: str, reason: str) -> None:
    _UNAVAILABLE[name] = reason

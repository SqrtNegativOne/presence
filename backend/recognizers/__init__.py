"""
recognizers/ — pluggable face-recognition backends.

A recognizer is anything that can turn an image (BGR numpy array) into a list of
DetectedFace objects (bounding box + embedding). All matching, annotation, and
attendance code is recognizer-agnostic; new backends just register themselves in
registry.py.

Pick one by `name` from registry.list_available() — the user's choice is stored
on the `users.preferred_recognizer` column and travels with each request.
"""
from .base import DetectedFace, FaceRecognizer
from .registry import get_recognizer, list_available, default_name

__all__ = [
    "DetectedFace",
    "FaceRecognizer",
    "get_recognizer",
    "list_available",
    "default_name",
]

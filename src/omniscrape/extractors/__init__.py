"""Deterministic extraction layers, ordered from strongest to broadest signal."""

from .common import ExtractionCandidate
from .heuristic import extract_heuristic
from .readability import extract_readability
from .structured import extract_structured

__all__ = [
    "ExtractionCandidate",
    "extract_heuristic",
    "extract_readability",
    "extract_structured",
]

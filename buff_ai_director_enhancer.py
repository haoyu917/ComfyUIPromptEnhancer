"""Backward-compatible import shim for BUFF AI Director V3."""

try:
    from .node import BuffAIDirectorEnhancer
except ImportError:  # Standalone test/import fallback.
    from node import BuffAIDirectorEnhancer

__all__ = ["BuffAIDirectorEnhancer"]

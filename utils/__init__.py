"""Recursively strip bytes from workflow and HTTP payloads."""

from __future__ import annotations

from typing import Any


def json_safe(value: Any) -> Any:
    """Return a JSON-serializable copy, dropping raw binary values."""
    if isinstance(value, (bytes, bytearray)):
        return None
    if isinstance(value, dict):
        return {
            k: json_safe(v)
            for k, v in value.items()
            if not isinstance(v, (bytes, bytearray))
        }
    if isinstance(value, list):
        return [json_safe(v) for v in value if not isinstance(v, (bytes, bytearray))]
    if isinstance(value, tuple):
        return tuple(json_safe(v) for v in value if not isinstance(v, (bytes, bytearray)))
    return value


__all__ = ["json_safe"]

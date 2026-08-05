"""Tests for bytes stripping utility."""

from utils.json_safe import json_safe


def test_nested_bytes_removed():
    assert json_safe({"x": {"y": b"bin"}}) == {"x": {}}

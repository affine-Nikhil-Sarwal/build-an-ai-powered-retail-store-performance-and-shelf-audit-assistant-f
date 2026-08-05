"""Extract JSON objects/arrays from messy LLM text.

Handles:
* bare JSON
* markdown fences (`` ```json ... ``` ``)
* leading/trailing prose around a JSON value
* nested braces/brackets (depth-aware, string-aware — not ``{.*}`` regex)

Import as ``config.llm_json`` in generated repos (seeded by
``seed_runtime_harness``). Catalog packages under ``agent_library/`` load the
same file via ``load_llm_json_module()`` when ``config`` is not on ``sys.path``.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_NOISE = (
    "Happy with the answer",
)


class LLMJsonParseError(ValueError):
    """Raised when LLM text does not contain a parseable JSON value."""

    def __init__(self, message: str, *, preview: str = "") -> None:
        self.preview = preview
        detail = message
        if preview:
            clipped = preview if len(preview) <= 240 else preview[:240] + "…"
            detail = f"{message} Preview={clipped!r}"
        super().__init__(detail)


def _strip_known_noise(text: str) -> str:
    cleaned = (text or "").strip()
    for noise in _TRAILING_NOISE:
        cleaned = cleaned.replace(noise, "")
    return cleaned.strip()


def _scan_balanced_end(text: str, start: int) -> int | None:
    """Return inclusive end index of the JSON value starting at ``start``."""
    if start < 0 or start >= len(text) or text[start] not in "{[":
        return None
    pairs = {"{": "}", "[": "]"}
    stack: list[str] = []
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in pairs:
            stack.append(pairs[ch])
            continue
        if ch in "}]":
            if not stack or stack[-1] != ch:
                return None
            stack.pop()
            if not stack:
                return i
    return None


def _iter_balanced_slices(text: str) -> list[str]:
    slices: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "{[":
            end = _scan_balanced_end(text, i)
            if end is not None:
                slices.append(text[i : end + 1])
                i = end + 1
                continue
        i += 1
    return slices


def _loads(candidate: str) -> Any:
    return json.loads(candidate)


def extract_json_value(text: str) -> Any:
    """
    Parse the primary JSON value from LLM output.

    Raises ``LLMJsonParseError`` when no valid JSON object/array/scalar can be
    recovered — never returns a silent empty dict.
    """
    raw = text if isinstance(text, str) else str(text or "")
    cleaned = _strip_known_noise(raw)
    if not cleaned:
        raise LLMJsonParseError("LLM response is empty; expected JSON.", preview=raw)

    # 1) Whole string (after light fence stripping) as JSON.
    stripped_fences = cleaned.replace("```json", "```").strip()
    if stripped_fences.startswith("```") and stripped_fences.endswith("```"):
        stripped_fences = stripped_fences[3:-3].strip()
        if stripped_fences.lower().startswith("json"):
            stripped_fences = stripped_fences[4:].lstrip()
    try:
        return _loads(stripped_fences)
    except json.JSONDecodeError:
        pass

    # 2) Markdown fences — prefer the first fence body that parses.
    fence_errors: list[str] = []
    for match in _FENCE_RE.finditer(cleaned):
        body = match.group(1).strip()
        try:
            return _loads(body)
        except json.JSONDecodeError as exc:
            fence_errors.append(str(exc))
            for slice_ in _iter_balanced_slices(body):
                try:
                    return _loads(slice_)
                except json.JSONDecodeError as inner:
                    fence_errors.append(str(inner))

    # 3) Depth-aware scan of the full text (nested braces safe).
    decode_errors: list[str] = list(fence_errors)
    for slice_ in _iter_balanced_slices(cleaned):
        try:
            return _loads(slice_)
        except json.JSONDecodeError as exc:
            decode_errors.append(str(exc))

    reason = "Could not extract parseable JSON from LLM response."
    if decode_errors:
        reason = f"{reason} Last decode error: {decode_errors[-1]}"
    raise LLMJsonParseError(reason, preview=cleaned)


def extract_json_dict(text: str) -> dict[str, Any]:
    """Like ``extract_json_value`` but requires a JSON object."""
    value = extract_json_value(text)
    if not isinstance(value, dict):
        raise LLMJsonParseError(
            f"Expected a JSON object, got {type(value).__name__}.",
            preview=(text or "")[:240],
        )
    return value


def try_extract_json_dict(text: str) -> dict[str, Any] | None:
    """Soft wrapper for chain usability checks — ``None`` when not a JSON object."""
    try:
        return extract_json_dict(text)
    except LLMJsonParseError:
        return None


def parse_message_content(content: str) -> dict[str, Any]:
    """Chain-helper soft parse: JSON object or ``{}`` when unusable."""
    return try_extract_json_dict(content) or {}


def load_from_caller_file(caller_file: str) -> Any:
    """Load this module for an ``agent_library`` caller given its ``__file__``."""
    try:
        from config import llm_json as mod  # type: ignore[attr-defined]

        return mod
    except ImportError:
        pass

    caller = Path(caller_file).resolve()
    # agent_library/<pkg>/{agent,chain_helpers}.py → backend/cursor_codegen/...
    for parent in caller.parents:
        path = parent / "cursor_codegen" / "runtime_seed" / "config" / "llm_json.py"
        if path.is_file():
            spec = importlib.util.spec_from_file_location("_llm_json_seed", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise ImportError(f"Unable to load llm_json.py from caller {caller_file}")


__all__ = [
    "LLMJsonParseError",
    "extract_json_dict",
    "extract_json_value",
    "load_from_caller_file",
    "parse_message_content",
    "try_extract_json_dict",
]

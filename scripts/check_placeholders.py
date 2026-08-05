#!/usr/bin/env python3
"""Fail the build if application code contains placeholders, mocks, or fake data.

Seeded by Agentic LaunchPad into every generated workflow repo. Scans first-party
application code for markers of non-runnable or faked implementations and exits
non-zero on any finding, so CI (and ``make check``) block a repository that only
*looks* complete. The goal: a repo that is genuinely runnable against real input
after ``pip install`` + real ``.env`` — never one held together by stubs.

Excluded from scanning (legitimate homes for the patterns below):
  - tests/                 mocks / fixtures are allowed here
  - examples/              real sample INPUT data, not logic
  - scripts/               this tool defines the patterns it searches for
  - agent_library/reuse/   frozen third-party source — not ours to police
  - agent_library/base/    seeded framework stub (has abstract raises)
  - agent_library/__init__.py  seeded framework stub
  - dotdirs, __pycache__, virtualenvs, build artifacts

Usage:  python scripts/check_placeholders.py   (exit 0 = clean, 1 = findings)
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# NOTE: do NOT list "build" here — real build nodes live under agent_library/build/.
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
}
EXCLUDE_PREFIXES = (
    "tests/",
    "examples/",
    "scripts/",
    "agents/reused/",
    "agents/base/",
    "agent_library/reuse/",
    "agent_library/base/",
)
EXCLUDE_EXACT = {"agents/__init__.py", "agent_library/__init__.py"}

# (pattern, human message). Matched line-by-line against application .py files.
TEXT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(TODO|FIXME|XXX)\b"), "leftover TODO/FIXME/XXX marker"),
    (re.compile(r"\braise\s+NotImplementedError\b"), "NotImplementedError in shipped code"),
    (re.compile(r"\b(MagicMock|AsyncMock)\b"), "mock object used outside tests/"),
    (
        re.compile(r"\bunittest\.mock\b|\bfrom\s+unittest\s+import\s+mock\b"),
        "unittest.mock used outside tests/",
    ),
    (re.compile(r"@patch\b|\bmonkeypatch\b"), "patch/monkeypatch used outside tests/"),
    (
        re.compile(r"\b(dummy|placeholder|hardcoded|canned)\w*", re.IGNORECASE),
        "dummy/placeholder/hardcoded/canned identifier",
    ),
    (re.compile(r"\bfake_\w+|\b\w+_fake\b", re.IGNORECASE), "fake_* identifier"),
]

# Function decorators that legitimately allow an empty body.
_ALLOWED_EMPTY_DECORATORS = ("abstract", "overload")


class Finding:
    __slots__ = ("path", "line", "message")

    def __init__(self, path: str, line: int, message: str) -> None:
        self.path = path
        self.line = line
        self.message = message

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def _is_excluded(rel_posix: str) -> bool:
    if rel_posix in EXCLUDE_EXACT:
        return True
    return any(rel_posix.startswith(prefix) for prefix in EXCLUDE_PREFIXES)


def _iter_py_files():
    for path in sorted(ROOT.rglob("*.py")):
        rel_parts = path.relative_to(ROOT).parts
        if any(p in EXCLUDE_DIR_NAMES or p.startswith(".") for p in rel_parts[:-1]):
            continue
        rel_posix = "/".join(rel_parts)
        if _is_excluded(rel_posix):
            continue
        yield path, rel_posix


def _scan_text(rel_posix: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, message in TEXT_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(rel_posix, lineno, message))
    return findings


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(getattr(node, "value", None), ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_ellipsis(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(getattr(node, "value", None), ast.Constant)
        and node.value.value is Ellipsis
    )


def _has_allowed_empty_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        name = ""
        if isinstance(dec, ast.Name):
            name = dec.id
        elif isinstance(dec, ast.Attribute):
            name = dec.attr
        elif isinstance(dec, ast.Call):
            target = dec.func
            name = getattr(target, "id", "") or getattr(target, "attr", "")
        if any(tag in name.lower() for tag in _ALLOWED_EMPTY_DECORATORS):
            return True
    return False


def _empty_body(body: list[ast.stmt]) -> bool:
    """True when a function has no real implementation (only docstring/pass/...)."""
    stmts = [s for s in body if not _is_docstring(s)]
    if not stmts:
        return True  # docstring-only or truly empty
    if len(stmts) == 1 and (isinstance(stmts[0], ast.Pass) or _is_ellipsis(stmts[0])):
        return True
    return False


def _scan_ast(rel_posix: str, text: str) -> list[Finding]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [Finding(rel_posix, exc.lineno or 0, f"file does not parse: {exc.msg}")]

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _has_allowed_empty_decorator(node):
                continue
            if _empty_body(node.body):
                findings.append(
                    Finding(
                        rel_posix,
                        node.lineno,
                        f"function '{node.name}' has no implementation (empty body)",
                    )
                )
    return findings


def scan(root: Path | None = None) -> list[Finding]:
    """Return all placeholder/mock findings under ``root`` (defaults to repo root)."""
    global ROOT
    if root is not None:
        ROOT = root.resolve()
    findings: list[Finding] = []
    for path, rel_posix in _iter_py_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(_scan_text(rel_posix, text))
        findings.extend(_scan_ast(rel_posix, text))
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print(
            f"[check_placeholders] {len(findings)} placeholder/mock/fake issue(s) found:",
            file=sys.stderr,
        )
        for line in sorted({str(f) for f in findings}):
            print(f"  {line}", file=sys.stderr)
        print(
            "Application code must contain real implementations against real input. "
            "See the ANTI-PLACEHOLDER CONTRACT.",
            file=sys.stderr,
        )
        return 1
    print("[check_placeholders] OK — no placeholders, mocks, or fake data in application code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

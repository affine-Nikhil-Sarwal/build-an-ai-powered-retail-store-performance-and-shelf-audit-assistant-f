"""Adapter functions for I/O shape conversion between workflow nodes.

LaunchPad seeds frozen reuse agents under ``agents/reused/``. When a reuse
node's output does not match the next node's expected input (reuse-to-build,
build-to-reuse, or reuse-to-reuse), add small pure conversion functions here
(one file per logical adapter group) and reference them from ``run_workflow.py``.
Never modify files under ``agents/reused/``.

When shaping evidence from a Quin/SQL-based node for a downstream conflict-gate
or synthesis node, prefer non-empty ``query_results`` over any
insufficiency-flagged natural-language summary (``query_answer`` / ``inference``
that claims no rows were available).

This package is adapters-only. It is not a BaseAgent / registry /
WorkflowExecutor framework — those symbols are not provided here.
Import framework types from the seeded ``agents`` package root when needed.
"""

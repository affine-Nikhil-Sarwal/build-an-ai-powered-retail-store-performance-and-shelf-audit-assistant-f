"""Inject orchestrator workflow context for manager drill-down output."""

from __future__ import annotations

from typing import Any


def build_drilldown_input(
    *,
    brief_draft: dict[str, Any],
    recommendations: list[dict[str, Any]],
    workflow_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "brief_draft": brief_draft,
        "recommendations": recommendations,
        "workflow_context": workflow_context,
    }

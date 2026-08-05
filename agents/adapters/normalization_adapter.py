"""Map document and vision findings into findings-normalization inputs."""

from __future__ import annotations

from typing import Any


def build_normalization_input(
    *,
    report_findings: dict[str, Any] | None = None,
    visual_findings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if report_findings is not None:
        payload["report_findings"] = report_findings
    if visual_findings is not None:
        payload["visual_findings"] = visual_findings
    return payload

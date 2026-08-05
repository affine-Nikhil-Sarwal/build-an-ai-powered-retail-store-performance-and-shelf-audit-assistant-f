"""Findings Normalization — unified issue schema with evidence refs."""

from __future__ import annotations

import uuid
from typing import Any

from config.settings import Settings


def _from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for finding in report.get("prior_findings") or []:
        issues.append(
            {
                "issue_id": str(uuid.uuid4()),
                "source": "report",
                "category": finding.get("category") or "general",
                "description": finding.get("description") or "",
                "severity": finding.get("severity") or "medium",
                "evidence_refs": [
                    {
                        "type": "report_excerpt",
                        "path_or_excerpt": finding.get("report_excerpt") or "",
                        "row_index": None,
                        "page_ref": finding.get("page_ref"),
                    }
                ],
                "recurrence_hint": False,
                "timestamps": {},
            }
        )
    return issues


def _from_visual(visual: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for finding in visual.get("issues") or []:
        issues.append(
            {
                "issue_id": str(uuid.uuid4()),
                "source": "photo",
                "category": finding.get("issue_type") or "shelf_issue",
                "description": finding.get("description") or "",
                "severity": "high" if finding.get("issue_type") == "stockout" else "medium",
                "evidence_refs": [
                    {
                        "type": "photo",
                        "path_or_excerpt": finding.get("image_path") or "",
                        "row_index": finding.get("row_index"),
                        "page_ref": None,
                    }
                ],
                "recurrence_hint": False,
                "timestamps": {},
            }
        )
    return issues


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    report = payload.get("report_findings")
    visual = payload.get("visual_findings")
    issues: list[dict[str, Any]] = []
    if isinstance(report, dict):
        issues.extend(_from_report(report))
    if isinstance(visual, dict):
        issues.extend(_from_visual(visual))
    warning = None
    if not issues:
        warning = "No findings from document or vision branches"
    return {"normalized_findings": {"issues": issues, "warning": warning}}

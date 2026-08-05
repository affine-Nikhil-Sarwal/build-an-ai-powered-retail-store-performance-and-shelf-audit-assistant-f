"""Evidence Merge Gate — photo overrides report on present-state conflicts."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from config.settings import Settings


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    normalized = payload.get("normalized_findings") or {}
    raw_issues = list(normalized.get("issues") or [])
    merged: list[dict[str, Any]] = []
    merge_notes: list[str] = []
    photo_by_category: dict[str, list[dict[str, Any]]] = {}
    report_by_category: dict[str, list[dict[str, Any]]] = {}

    for issue in raw_issues:
        cat = issue.get("category") or "general"
        if issue.get("source") == "photo":
            photo_by_category.setdefault(cat, []).append(issue)
        else:
            report_by_category.setdefault(cat, []).append(issue)

    handled_report_ids: set[str] = set()
    for cat, photo_issues in photo_by_category.items():
        for photo_issue in photo_issues:
            conflict_flags: list[str] = []
            report_context: list[dict[str, Any]] = []
            for report_issue in report_by_category.get(cat, []):
                sim = _similar(photo_issue.get("description", ""), report_issue.get("description", ""))
                if sim >= 0.45 and sim < 0.85:
                    conflict_flags.append("present_state_conflict")
                    merge_notes.append(
                        f"Photo observation overrides report claim in category {cat}"
                    )
                    report_context.append(
                        {
                            **report_issue,
                            "status": "historical_context",
                        }
                    )
                    handled_report_ids.add(report_issue.get("issue_id", ""))
                elif sim >= 0.85:
                    report_context.append(report_issue)
                    handled_report_ids.add(report_issue.get("issue_id", ""))
            merged.append(
                {
                    **photo_issue,
                    "source": "both" if report_context else "photo",
                    "conflict_flags": conflict_flags,
                    "photo_authoritative_fields": ["description", "severity"],
                    "report_context_fields": report_context,
                    "merge_notes": merge_notes[-len(conflict_flags) :] if conflict_flags else [],
                }
            )

    for cat, report_issues in report_by_category.items():
        for report_issue in report_issues:
            if report_issue.get("issue_id") in handled_report_ids:
                continue
            merged.append(
                {
                    **report_issue,
                    "conflict_flags": [],
                    "photo_authoritative_fields": [],
                    "report_context_fields": [report_issue],
                    "merge_notes": ["Report-only historical context"],
                }
            )

    image_paths = {
        ref.get("path_or_excerpt")
        for issue in raw_issues
        if issue.get("source") == "photo"
        for ref in issue.get("evidence_refs") or []
    }
    if len(image_paths) > 1:
        merge_notes.append("Multiple photos may show inconsistent shelf conditions")

    return {
        "merged_evidence_set": {
            "issues": merged,
            "conflict_flags": [n for i in merged for n in i.get("conflict_flags") or []],
            "merge_notes": merge_notes,
        }
    }

"""Manager Drill-down Output — final deliverables with side-by-side evidence."""

from __future__ import annotations

from typing import Any

from config.settings import Settings


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    brief = payload.get("brief_draft") or {}
    recommendations = list(payload.get("recommendations") or [])
    ctx = payload.get("workflow_context") or {}

    prioritized = list(ctx.get("prioritized_issues") or payload.get("prioritized_issues") or [])
    scored = ctx.get("scored_issues") or {}
    merged = ctx.get("merged_evidence_set") or {}
    usable = ctx.get("usable_shelf_images") or {}
    package = ctx.get("validated_upload_package") or {}

    narrative = (
        f"{brief.get('title', 'Shelf Audit Brief')}\n\n"
        f"{brief.get('executive_summary', '')}\n\n"
        f"Disclaimer: {brief.get('confidence_disclaimer', '')}"
    ).strip()

    drill_down: list[dict[str, Any]] = []
    for issue in prioritized:
        photo_refs = [
            ref
            for ref in issue.get("evidence_refs") or []
            if ref.get("type") == "photo"
        ]
        report_refs = [
            ref
            for ref in issue.get("evidence_refs") or []
            if ref.get("type") == "report_excerpt"
        ]
        report_context = issue.get("report_context_fields") or []
        drill_down.append(
            {
                "issue_id": issue.get("issue_id"),
                "photo_paths": [r.get("path_or_excerpt") for r in photo_refs if r.get("path_or_excerpt")],
                "report_excerpt": (report_refs[0].get("path_or_excerpt") if report_refs else None)
                or (
                    report_context[0].get("description")
                    if report_context and isinstance(report_context[0], dict)
                    else "evidence unavailable"
                ),
                "conflict_notes": issue.get("merge_notes") or issue.get("conflict_flags") or [],
                "side_by_side": {
                    "photo": photo_refs[0].get("path_or_excerpt") if photo_refs else None,
                    "report": report_refs[0].get("path_or_excerpt") if report_refs else None,
                },
            }
        )

    rejected = [img.get("path") for img in (usable.get("rejected_images") or []) if img.get("path")]
    confidence_notes = {
        "overall_confidence": (
            sum(float(i.get("confidence") or 0) for i in (scored.get("issues") or prioritized))
            / max(len(prioritized) or len(scored.get("issues") or []), 1)
        ),
        "per_issue_flags": [
            {
                "issue_id": i.get("issue_id"),
                "insufficient_evidence": i.get("insufficient_evidence"),
                "conflict_detected": i.get("conflict_detected"),
            }
            for i in (scored.get("issues") or prioritized)
        ],
        "rejected_image_paths": rejected,
        "ocr_quality_notes": package.get("ocr_quality_note"),
        "merge_notes": merged.get("merge_notes") or [],
    }

    return {
        "one_page_narrative_executive_brief": narrative,
        "prioritized_issue_list": prioritized,
        "issue_level_drill_down_with_side_by_side_photo_evidence_and_report_excerpts": drill_down,
        "free_form_corrective_action_recommendations": recommendations,
        "confidence_notes_and_insufficient_evidence_flags": confidence_notes,
    }

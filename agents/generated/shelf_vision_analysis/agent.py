"""Shelf Vision Analysis — row-aware visible issue detection."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient

_DEFAULT_QUERY = (
    "Identify visible stock-outs, low facings, misplaced products, and empty shelf gaps. "
    "Only report what is visibly evident."
)

_VISION_SYSTEM = (
    "Analyze retail shelf row images. Return JSON {\"issues\": [{issue_type, description, "
    "image_path, row_index, bbox, confidence, visible_only}], \"row_analyses\": [], "
    "\"reasoning\": string, \"insufficient_evidence_flags\": []}. visible_only must be true."
)


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    rows = payload.get("detected_rows") or []
    if not rows:
        return {
            "visual_findings": {
                "issues": [],
                "row_analyses": [],
                "reasoning": "No row crops available",
                "insufficient_evidence_flags": ["no_rows"],
            }
        }

    audit_query = payload.get("audit_query") or _DEFAULT_QUERY
    if dry_run:
        return {
            "visual_findings": {
                "issues": [],
                "row_analyses": [
                    {
                        "row_index": row.get("row_index"),
                        "crop_path": row.get("crop_path"),
                        "note": "Vision analysis skipped in dry_run",
                    }
                    for row in rows
                ],
                "reasoning": "Dry-run mode: vision LLM skipped",
                "insufficient_evidence_flags": [],
            }
        }

    llm = AzureOpenAIClient(settings)
    issues: list[dict[str, Any]] = []
    row_analyses: list[dict[str, Any]] = []
    insufficient: list[str] = []
    for row in sorted(rows, key=lambda r: (r.get("image_path", ""), r.get("row_index", 0))):
        crop = row.get("crop_path")
        if not crop:
            insufficient.append(f"row_{row.get('row_index')}_missing_crop")
            continue
        try:
            parsed = llm.vision_json(
                system=_VISION_SYSTEM,
                user_text=f"{audit_query}\nRow index: {row.get('row_index')}",
                image_paths=[crop],
                max_tokens=900,
            )
            row_issues = list(parsed.get("issues") or [])
            for issue in row_issues:
                issue.setdefault("visible_only", True)
                issue.setdefault("image_path", row.get("image_path"))
                issue.setdefault("row_index", row.get("row_index"))
                issues.append(issue)
            row_analyses.append(
                {
                    "row_index": row.get("row_index"),
                    "crop_path": crop,
                    "analysis": parsed.get("reasoning") or "",
                }
            )
            insufficient.extend(list(parsed.get("insufficient_evidence_flags") or []))
        except Exception as exc:
            insufficient.append(f"row_{row.get('row_index')}_vision_error:{exc}")

    return {
        "visual_findings": {
            "issues": issues,
            "row_analyses": row_analyses,
            "reasoning": f"Analyzed {len(row_analyses)} row crops",
            "insufficient_evidence_flags": insufficient,
        }
    }

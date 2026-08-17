"""Shelf Vision Analysis — row-aware visible issue detection."""

from __future__ import annotations

import json
from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient

_DEFAULT_QUERY = (
    "Identify every visible product facing, stock-out, low facings, misplaced products, "
    "and empty shelf gaps. Scan the full row left-to-right and report any product regions "
    "that may have been missed by upstream detection. Only report what is visibly evident."
)

_VISION_SYSTEM = (
    "Analyze retail shelf row images for product availability and placement. "
    "Use the provided detected product bounding boxes as hints — verify each region, "
    "add any missed visible products, and flag gaps or stock-outs between detections. "
    "Return JSON {\"issues\": [{issue_type, description, image_path, row_index, bbox, "
    "confidence, visible_only}], \"row_analyses\": [{row_index, detected_product_count, "
    "notes}], \"reasoning\": string, \"insufficient_evidence_flags\": []}. "
    "visible_only must be true. issue_type examples: stockout, low_facings, misplaced, gap."
)


def _products_for_row(products: list[dict[str, Any]], row_index: int) -> list[dict[str, Any]]:
    return [p for p in products if p.get("row_index") == row_index]


def _format_product_hints(products: list[dict[str, Any]]) -> str:
    if not products:
        return "No upstream product detections for this row — scan the entire row carefully."
    compact = [
        {
            "bbox": p.get("bbox"),
            "label": p.get("label"),
            "confidence": p.get("confidence"),
        }
        for p in products
    ]
    return (
        f"Upstream object detection found {len(products)} product region(s) in this row. "
        f"Verify each bbox and identify any additional visible products or gaps:\n"
        f"{json.dumps(compact, separators=(',', ':'))}"
    )


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    rows = payload.get("detected_rows") or []
    products = payload.get("products") or []
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
                        "detected_product_count": len(_products_for_row(products, row.get("row_index", 0))),
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
        row_index = row.get("row_index", 0)
        if not crop:
            insufficient.append(f"row_{row_index}_missing_crop")
            continue
        row_products = _products_for_row(products, row_index)
        product_hints = _format_product_hints(row_products)
        try:
            parsed = llm.vision_json(
                system=_VISION_SYSTEM,
                user_text=(
                    f"{audit_query}\n"
                    f"Row index: {row_index}\n"
                    f"{product_hints}"
                ),
                image_paths=[crop],
                max_tokens=1200,
            )
            row_issues = list(parsed.get("issues") or [])
            for issue in row_issues:
                issue.setdefault("visible_only", True)
                issue.setdefault("image_path", row.get("image_path"))
                issue.setdefault("row_index", row_index)
                issues.append(issue)
            parsed_analyses = list(parsed.get("row_analyses") or [])
            if parsed_analyses:
                row_analyses.extend(parsed_analyses)
            else:
                row_analyses.append(
                    {
                        "row_index": row_index,
                        "crop_path": crop,
                        "detected_product_count": len(row_products),
                        "analysis": parsed.get("reasoning") or "",
                    }
                )
            insufficient.extend(list(parsed.get("insufficient_evidence_flags") or []))
        except Exception as exc:
            insufficient.append(f"row_{row_index}_vision_error:{exc}")

    return {
        "visual_findings": {
            "issues": issues,
            "row_analyses": row_analyses,
            "reasoning": f"Analyzed {len(row_analyses)} row crops with {len(products)} upstream product detections",
            "insufficient_evidence_flags": insufficient,
        }
    }

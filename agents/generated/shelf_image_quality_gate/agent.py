"""Shelf Image Quality Gate — blur/dark/obstruction detection."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from integrations.vision_quality import VisionQualityChecker


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    if payload.get("run_vision_path") is False:
        return {
            "usable_shelf_images": {
                "images": [],
                "rejected_images": [],
                "overall_usable_count": 0,
                "skipped": True,
            }
        }

    package = payload.get("validated_upload_package") or {}
    image_paths = package.get("image_paths") or []
    checker = VisionQualityChecker()
    images: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for path in image_paths:
        result = checker.assess(path)
        entry = {
            "path": result["path"],
            "quality_score": result["quality_score"],
            "usable": result["usable"],
            "issues": result["issues"],
            "insufficient_evidence": result["insufficient_evidence"],
        }
        if result["usable"]:
            images.append(entry)
        else:
            rejected.append(entry)

    return {
        "usable_shelf_images": {
            "images": images,
            "rejected_images": rejected,
            "overall_usable_count": len(images),
        }
    }

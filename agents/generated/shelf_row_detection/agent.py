"""Shelf Row Detection — row crops and product bounding boxes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config.settings import Settings
from integrations.row_detector import RowDetector

logger = logging.getLogger(__name__)


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    usable = payload.get("usable_shelf_images") or {}
    images = usable.get("images") or []
    if not images:
        return {"detected_rows": [], "products": []}

    package = payload.get("validated_upload_package") or {}
    storage_root = package.get("storage_root") or str(settings.upload_path())
    crops_dir = Path(storage_root) / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    image_paths: list[str] = []
    for image in images:
        path = image.get("path") or image.get("image_path")
        if not path:
            logger.warning("Usable shelf image is missing a path; skipping")
            continue
        image_paths.append(path)

    detector = RowDetector(settings)
    detected_rows, products = detector.detect_batch(image_paths, crops_dir)
    return {"detected_rows": detected_rows, "products": products}

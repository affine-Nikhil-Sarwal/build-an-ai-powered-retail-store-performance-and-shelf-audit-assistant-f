"""Shelf Row Detection — row crops and product bounding boxes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config.settings import Settings
from integrations.row_detector import RowDetector


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    usable = payload.get("usable_shelf_images") or {}
    images = usable.get("images") or []
    if not images:
        return {"detected_rows": [], "products": []}

    package = payload.get("validated_upload_package") or {}
    storage_root = package.get("storage_root") or str(settings.upload_path())
    crops_dir = Path(storage_root) / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    detector = RowDetector(settings)
    all_rows: list[dict[str, Any]] = []
    all_products: list[dict[str, Any]] = []
    for image in images:
        path = image.get("path") or image.get("image_path")
        if not path:
            continue
        rows, products = detector.detect(path, crops_dir)
        all_rows.extend(rows)
        all_products.extend(products)
    return {"detected_rows": all_rows, "products": all_products}

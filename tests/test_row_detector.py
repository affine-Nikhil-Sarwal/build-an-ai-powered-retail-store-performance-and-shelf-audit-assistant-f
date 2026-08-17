"""Unit tests for shelf row and product detection."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from config.settings import get_settings
from integrations.row_detector import RowDetector, _detect_products_in_row, _horizontal_row_boundaries


ROOT = Path(__file__).resolve().parent.parent


def _synthetic_shelf_image(path: Path, *, rows: int = 3, products_per_row: int = 6) -> None:
    """Create a synthetic shelf image with horizontal dividers and product blocks."""
    width, height = 640, 480
    image = np.full((height, width, 3), 220, dtype=np.uint8)
    row_height = height // rows
    colors = [(180, 80, 60), (60, 120, 180), (80, 160, 80), (160, 120, 60)]
    for row in range(rows):
        y0 = row * row_height
        y1 = y0 + row_height - 8
        cv2.line(image, (0, y1 + 4), (width, y1 + 4), (40, 40, 40), 3)
        slot_width = width // products_per_row
        for col in range(products_per_row):
            x0 = col * slot_width + 8
            x1 = x0 + slot_width - 16
            color = colors[(row + col) % len(colors)]
            cv2.rectangle(image, (x0, y0 + 10), (x1, y1 - 6), color, -1)
            cv2.rectangle(image, (x0, y0 + 10), (x1, y1 - 6), (30, 30, 30), 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


@pytest.fixture
def synthetic_shelf(tmp_path: Path) -> Path:
    path = tmp_path / "shelf.jpg"
    _synthetic_shelf_image(path)
    return path


def test_horizontal_row_boundaries_finds_multiple_rows():
    gray = np.zeros((360, 480), dtype=np.uint8)
    for y in (0, 120, 240):
        cv2.rectangle(gray, (20, y + 10), (460, y + 100), 180, -1)
        cv2.line(gray, (0, y + 110), (480, y + 110), 255, 4)
    rows = _horizontal_row_boundaries(gray, min_rows=2, max_rows=6)
    assert len(rows) >= 2


def test_detect_products_in_row_finds_multiple_products(synthetic_shelf: Path):
    image = cv2.imread(str(synthetic_shelf))
    assert image is not None
    h, w = image.shape[:2]
    row_h = h // 3
    crop = image[0:row_h, :]
    products = _detect_products_in_row(crop, 0, w, row_h)
    assert len(products) >= 4


def test_row_detector_detects_more_products_than_legacy_cap(synthetic_shelf: Path, tmp_path: Path):
    settings = get_settings(dry_run=True)
    detector = RowDetector(settings)
    crops_dir = tmp_path / "crops"
    crops_dir.mkdir()
    rows, products = detector.detect(str(synthetic_shelf), crops_dir)
    assert len(rows) >= 2
    assert len(products) >= 8
    assert all(p.get("label") == "product_facing" for p in products)
    assert all(0.0 < float(p.get("confidence", 0)) <= 1.0 for p in products)


def test_row_detector_writes_row_crops(synthetic_shelf: Path, tmp_path: Path):
    settings = get_settings(dry_run=True)
    detector = RowDetector(settings)
    crops_dir = tmp_path / "crops"
    crops_dir.mkdir()
    rows, _products = detector.detect(str(synthetic_shelf), crops_dir)
    for row in rows:
        assert Path(row["crop_path"]).is_file()


def test_vision_analysis_uses_product_hints_in_dry_run():
    from agents.generated.shelf_vision_analysis.agent import run

    settings = get_settings(dry_run=True)
    out = run(
        {
            "detected_rows": [
                {"row_index": 1, "crop_path": "/tmp/row1.jpg", "image_path": "/tmp/shelf.jpg"},
            ],
            "products": [
                {"row_index": 1, "bbox": [10, 20, 40, 80], "label": "product_facing", "confidence": 0.7},
                {"row_index": 1, "bbox": [60, 20, 40, 80], "label": "product_facing", "confidence": 0.65},
            ],
        },
        settings=settings,
        dry_run=True,
    )
    analyses = out["visual_findings"]["row_analyses"]
    assert analyses[0]["detected_product_count"] == 2

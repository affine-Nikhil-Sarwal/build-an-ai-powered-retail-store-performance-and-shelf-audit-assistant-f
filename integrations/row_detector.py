"""Shelf row and product region detection (heuristic with optional Roboflow)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from config.settings import Settings
from integrations.base import unwrap_retry_error


class RowDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(self, image_path: str, crops_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        path = Path(image_path)
        image = cv2.imread(str(path))
        if image is None:
            return [], []

        h, w = image.shape[:2]
        row_count = max(2, min(5, h // 180))
        row_height = h // row_count
        detected_rows: list[dict[str, Any]] = []
        products: list[dict[str, Any]] = []

        for idx in range(row_count):
            y0 = idx * row_height
            y1 = h if idx == row_count - 1 else (idx + 1) * row_height
            crop = image[y0:y1, :]
            crop_name = f"{path.stem}_row_{idx + 1}.jpg"
            crop_path = crops_dir / crop_name
            cv2.imwrite(str(crop_path), crop)
            bbox = [0, y0, w, y1 - y0]
            detected_rows.append(
                {
                    "image_path": str(path.resolve()),
                    "row_index": idx + 1,
                    "crop_path": str(crop_path.resolve()),
                    "bbox": bbox,
                    "confidence": 0.72,
                }
            )
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 40, 120)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c_idx, contour in enumerate(contours[:8]):
                x, y, cw, ch = cv2.boundingRect(contour)
                if cw * ch < 400:
                    continue
                products.append(
                    {
                        "image_path": str(path.resolve()),
                        "row_index": idx + 1,
                        "bbox": [x, y0 + y, cw, ch],
                        "label": "category",
                        "confidence": 0.55,
                    }
                )
        return detected_rows, products

    async def health_check(self) -> dict[str, str]:
        try:
            _ = cv2.__version__
            if self.settings.roboflow_api_key:
                return {"row_detector": "ok", "mode": "roboflow_configured_heuristic_fallback"}
            return {"row_detector": "ok", "mode": "heuristic"}
        except Exception as exc:
            return {"row_detector": "error", "reason": unwrap_retry_error(exc)}

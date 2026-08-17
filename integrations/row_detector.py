"""Shelf row and product region detection (heuristic with optional Roboflow)."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np

from config.settings import Settings
from integrations.base import unwrap_retry_error

logger = logging.getLogger(__name__)


def _nms_boxes(
    boxes: list[tuple[int, int, int, int, float]],
    iou_threshold: float = 0.35,
) -> list[tuple[int, int, int, int, float]]:
    """Non-maximum suppression for overlapping detections."""
    if not boxes:
        return []
    boxes = sorted(boxes, key=lambda b: b[4], reverse=True)
    kept: list[tuple[int, int, int, int, float]] = []
    for box in boxes:
        x, y, w, h, conf = box
        suppress = False
        for kx, ky, kw, kh, _ in kept:
            ix = max(x, kx)
            iy = max(y, ky)
            iw = max(0, min(x + w, kx + kw) - ix)
            ih = max(0, min(y + h, ky + kh) - iy)
            inter = iw * ih
            union = w * h + kw * kh - inter
            if union > 0 and inter / union >= iou_threshold:
                suppress = True
                break
        if not suppress:
            kept.append(box)
    return kept


def _horizontal_row_boundaries(
    gray: np.ndarray,
    *,
    min_rows: int = 2,
    max_rows: int = 8,
) -> list[tuple[int, int]]:
    """Detect shelf row boundaries using horizontal edge projection."""
    h, _w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    sobel_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
    profile = np.mean(np.abs(sobel_y), axis=1)
    profile = cv2.GaussianBlur(profile.reshape(-1, 1), (1, 15), 0).flatten()

    threshold = float(np.percentile(profile, 75))
    candidates: list[int] = []
    for i in range(1, h - 1):
        if profile[i] >= threshold and profile[i] >= profile[i - 1] and profile[i] >= profile[i + 1]:
            candidates.append(i)

    merged: list[int] = []
    min_gap = max(40, h // (max_rows + 2))
    for y in sorted(candidates):
        if not merged or y - merged[-1] > min_gap:
            merged.append(y)

    boundaries = sorted({0, *merged, h})
    rows: list[tuple[int, int]] = []
    for i in range(len(boundaries) - 1):
        y0, y1 = boundaries[i], boundaries[i + 1]
        if y1 - y0 >= min_gap:
            rows.append((y0, y1))

    if len(rows) < min_rows:
        row_count = max(min_rows, min(max_rows, h // 120))
        row_height = h // row_count
        rows = []
        for idx in range(row_count):
            y0 = idx * row_height
            y1 = h if idx == row_count - 1 else (idx + 1) * row_height
            rows.append((y0, y1))

    return rows[:max_rows]


def _detect_products_in_row(
    crop: np.ndarray,
    y_offset: int,
    row_w: int,
    row_h: int,
) -> list[tuple[int, int, int, int, float]]:
    """Multi-pass product region detection within a shelf row crop."""
    min_area = max(80, int(row_w * row_h * 0.0008))
    max_products = max(16, row_w // 30)

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    candidates: list[tuple[int, int, int, int, float]] = []

    for low, high in ((20, 80), (40, 120), (60, 160)):
        edges = cv2.Canny(gray, low, high)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cw * ch
            if area < min_area:
                continue
            aspect = cw / max(ch, 1)
            if aspect < 0.15 or aspect > 8.0:
                continue
            if ch > row_h * 0.95 or cw > row_w * 0.95:
                continue
            fill = cv2.contourArea(contour) / max(area, 1)
            conf = min(0.92, 0.45 + fill * 0.3 + min(aspect, 1 / max(aspect, 0.01)) * 0.1)
            candidates.append((x, y_offset + y, cw, ch, conf))

    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15,
        4,
    )
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, max(3, row_h // 8)))
    morphed = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, vertical_kernel)
    contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        if area < min_area * 0.7:
            continue
        aspect = cw / max(ch, 1)
        if aspect < 0.1 or aspect > 6.0:
            continue
        conf = min(0.88, 0.5 + min(area / (row_w * row_h), 0.3))
        candidates.append((x, y_offset + y, cw, ch, conf))

    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    col_profile = np.mean(np.abs(sobel_x), axis=0)
    col_profile = cv2.GaussianBlur(col_profile.reshape(1, -1), (15, 1), 0).flatten()
    peak_thresh = float(np.percentile(col_profile, 60))
    peaks: list[int] = []
    for i in range(1, row_w - 1):
        if (
            col_profile[i] >= peak_thresh
            and col_profile[i] >= col_profile[i - 1]
            and col_profile[i] >= col_profile[i + 1]
        ):
            peaks.append(i)

    if len(peaks) >= 2:
        merged_peaks = [peaks[0]]
        min_col_gap = max(20, row_w // 40)
        for peak in peaks[1:]:
            if peak - merged_peaks[-1] >= min_col_gap:
                merged_peaks.append(peak)
        merged_peaks.append(row_w)
        y_margin = max(2, row_h // 20)
        for i in range(len(merged_peaks) - 1):
            x0 = merged_peaks[i]
            x1 = merged_peaks[i + 1]
            cw = x1 - x0
            if cw < max(15, row_w // 50):
                continue
            candidates.append((x0, y_offset + y_margin, cw, row_h - 2 * y_margin, 0.52))

    deduped = _nms_boxes(candidates, iou_threshold=0.35)
    row_area = max(row_w * row_h, 1)
    deduped = [b for b in deduped if (b[2] * b[3]) / row_area < 0.85]
    deduped.sort(key=lambda b: b[0])
    return deduped[:max_products]


class RowDetector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def detect(self, image_path: str, crops_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        path = Path(image_path)
        image = cv2.imread(str(path))
        if image is None:
            return [], []

        if self.settings.roboflow_api_key and self.settings.roboflow_model:
            try:
                return self._detect_roboflow(path, image, crops_dir)
            except Exception as exc:
                logger.warning("Roboflow detection failed for %s: %s; using heuristic fallback", path, exc)

        return self._detect_heuristic(path, image, crops_dir)

    def _detect_heuristic(
        self,
        path: Path,
        image: np.ndarray,
        crops_dir: Path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        row_bounds = _horizontal_row_boundaries(gray)

        detected_rows: list[dict[str, Any]] = []
        products: list[dict[str, Any]] = []

        for idx, (y0, y1) in enumerate(row_bounds):
            crop = image[y0:y1, :]
            crop_name = f"{path.stem}_row_{idx + 1}.jpg"
            crop_path = crops_dir / crop_name
            cv2.imwrite(str(crop_path), crop)
            row_h = y1 - y0
            detected_rows.append(
                {
                    "image_path": str(path.resolve()),
                    "row_index": idx + 1,
                    "crop_path": str(crop_path.resolve()),
                    "bbox": [0, y0, w, row_h],
                    "confidence": 0.78,
                }
            )
            for x, y, cw, ch, conf in _detect_products_in_row(crop, y0, w, row_h):
                products.append(
                    {
                        "image_path": str(path.resolve()),
                        "row_index": idx + 1,
                        "bbox": [x, y, cw, ch],
                        "label": "product_facing",
                        "confidence": round(conf, 3),
                    }
                )
        return detected_rows, products

    def _detect_roboflow(
        self,
        path: Path,
        image: np.ndarray,
        crops_dir: Path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        h, w = image.shape[:2]
        model = (self.settings.roboflow_model or "").strip().strip("/")
        api_key = (self.settings.roboflow_api_key or "").strip()
        url = f"https://detect.roboflow.com/{model}"
        ok, encoded = cv2.imencode(".jpg", image)
        if not ok:
            raise RuntimeError("failed to encode image for Roboflow")
        payload = base64.b64encode(encoded.tobytes()).decode("ascii")

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                url,
                params={"api_key": api_key},
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            result = response.json()

        predictions = list(result.get("predictions") or [])
        row_labels = {"shelf_row", "row", "shelf-row", "shelf row"}
        product_labels = {"product", "sku", "item", "product_facing", "category", "brand"}

        row_preds = [p for p in predictions if str(p.get("class", "")).lower() in row_labels]
        product_preds = [
            p
            for p in predictions
            if str(p.get("class", "")).lower() in product_labels
            or str(p.get("class", "")).lower() not in row_labels
        ]

        detected_rows: list[dict[str, Any]] = []
        products: list[dict[str, Any]] = []

        if row_preds:
            row_preds.sort(key=lambda p: float(p.get("y", 0)))
            for idx, pred in enumerate(row_preds):
                x = int(float(pred.get("x", 0)) - float(pred.get("width", w)) / 2)
                y = int(float(pred.get("y", 0)) - float(pred.get("height", h)) / 2)
                cw = int(float(pred.get("width", w)))
                ch = int(float(pred.get("height", h // max(len(row_preds), 1))))
                x = max(0, min(x, w - 1))
                y = max(0, min(y, h - 1))
                cw = max(1, min(cw, w - x))
                ch = max(1, min(ch, h - y))
                crop = image[y : y + ch, x : x + cw]
                crop_name = f"{path.stem}_row_{idx + 1}.jpg"
                crop_path = crops_dir / crop_name
                cv2.imwrite(str(crop_path), crop)
                detected_rows.append(
                    {
                        "image_path": str(path.resolve()),
                        "row_index": idx + 1,
                        "crop_path": str(crop_path.resolve()),
                        "bbox": [x, y, cw, ch],
                        "confidence": round(float(pred.get("confidence", 0.8)), 3),
                    }
                )
        else:
            detected_rows, heuristic_products = self._detect_heuristic(path, image, crops_dir)
            if heuristic_products:
                return detected_rows, heuristic_products

        for pred in product_preds:
            px = float(pred.get("x", 0))
            py = float(pred.get("y", 0))
            pw = float(pred.get("width", 0))
            ph = float(pred.get("height", 0))
            x = max(0, int(px - pw / 2))
            y = max(0, int(py - ph / 2))
            cw = max(1, int(pw))
            ch = max(1, int(ph))
            row_index = 1
            if detected_rows:
                row_index = min(
                    detected_rows,
                    key=lambda row: abs(py - (row["bbox"][1] + row["bbox"][3] / 2)),
                )["row_index"]
            products.append(
                {
                    "image_path": str(path.resolve()),
                    "row_index": row_index,
                    "bbox": [x, y, cw, ch],
                    "label": str(pred.get("class") or "product_facing"),
                    "confidence": round(float(pred.get("confidence", 0.7)), 3),
                }
            )

        if not products and detected_rows:
            for row in detected_rows:
                crop_path = Path(row["crop_path"])
                crop = cv2.imread(str(crop_path))
                if crop is None:
                    continue
                y0 = row["bbox"][1]
                row_h = row["bbox"][3]
                for x, y, cw, ch, conf in _detect_products_in_row(crop, y0, row["bbox"][2], row_h):
                    products.append(
                        {
                            "image_path": str(path.resolve()),
                            "row_index": row["row_index"],
                            "bbox": [x, y, cw, ch],
                            "label": "product_facing",
                            "confidence": round(conf, 3),
                        }
                    )
        return detected_rows, products

    async def health_check(self) -> dict[str, str]:
        try:
            _ = cv2.__version__
            if self.settings.roboflow_api_key and self.settings.roboflow_model:
                return {"row_detector": "ok", "mode": "roboflow"}
            if self.settings.roboflow_api_key:
                return {"row_detector": "ok", "mode": "roboflow_key_only_heuristic_fallback"}
            return {"row_detector": "ok", "mode": "heuristic"}
        except Exception as exc:
            return {"row_detector": "error", "reason": unwrap_retry_error(exc)}

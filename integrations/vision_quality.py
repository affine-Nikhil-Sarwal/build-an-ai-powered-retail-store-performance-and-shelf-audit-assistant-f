"""OpenCV-based shelf image quality heuristics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from integrations.base import unwrap_retry_error


class VisionQualityChecker:
    def assess(self, image_path: str) -> dict[str, Any]:
        path = Path(image_path)
        image = cv2.imread(str(path))
        if image is None:
            return {
                "path": str(path.resolve()),
                "quality_score": 0.0,
                "usable": False,
                "issues": ["unreadable_image"],
                "insufficient_evidence": True,
            }

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        h, w = gray.shape
        edge_density = float(np.mean(cv2.Canny(gray, 50, 150) > 0))

        issues: list[str] = []
        if lap_var < 60:
            issues.append("blur")
        if brightness < 45:
            issues.append("dark")
        if brightness > 230:
            issues.append("overexposed")
        if edge_density < 0.02:
            issues.append("obstructed_or_blank")
        if min(h, w) < 200:
            issues.append("partial_framing")

        score = min(1.0, max(0.0, (lap_var / 300.0) * 0.5 + (brightness / 255.0) * 0.3 + edge_density * 2.0))
        insufficient = bool(issues)
        usable = score >= 0.35 and "unreadable_image" not in issues and lap_var >= 40

        return {
            "path": str(path.resolve()),
            "quality_score": round(score, 3),
            "usable": usable and not insufficient,
            "issues": issues,
            "insufficient_evidence": insufficient or not usable,
        }

    async def health_check(self) -> dict[str, str]:
        try:
            _ = cv2.__version__
            return {"vision_quality": "ok"}
        except Exception as exc:
            return {"vision_quality": "error", "reason": unwrap_retry_error(exc)}

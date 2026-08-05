"""Compliance and policy validation for uploads."""

from __future__ import annotations

from pathlib import Path

ALLOWED_DOCUMENT_SUFFIXES = {".pdf", ".docx"}
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024


class PolicyValidator:
    """Advisory policy checks for retail audit uploads."""

    def validate_document(self, path: str) -> list[str]:
        violations: list[str] = []
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix not in ALLOWED_DOCUMENT_SUFFIXES:
            violations.append(f"Disallowed document type: {suffix or 'unknown'}")
        if p.exists() and p.stat().st_size > MAX_DOCUMENT_BYTES:
            violations.append("Document exceeds maximum size (25MB)")
        return violations

    def validate_image(self, path: str) -> list[str]:
        violations: list[str] = []
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix not in ALLOWED_IMAGE_SUFFIXES:
            violations.append(f"Disallowed image type: {suffix or 'unknown'}")
        if p.exists() and p.stat().st_size > MAX_IMAGE_BYTES:
            violations.append("Image exceeds maximum size (15MB)")
        return violations

    async def health_check(self) -> dict[str, str]:
        return {"policy_validator": "ok"}

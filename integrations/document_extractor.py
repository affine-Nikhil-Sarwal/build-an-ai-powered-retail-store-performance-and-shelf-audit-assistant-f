"""PDF/DOCX text extraction with OCR quality scoring."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from integrations.base import unwrap_retry_error


def _score_ocr_quality(text: str) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) < 120:
        return "poor"
    non_alpha = len(re.findall(r"[^A-Za-z0-9\s.,;:%\-()/$]", cleaned))
    ratio = non_alpha / max(len(cleaned), 1)
    if ratio > 0.25:
        return "poor"
    if len(cleaned) < 400 or ratio > 0.12:
        return "partial"
    return "good"


class DocumentExtractor:
    def extract(self, document_path: str) -> dict[str, Any]:
        path = Path(document_path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(path)
        if suffix == ".docx":
            return self._extract_docx(path)
        raise ValueError(f"Unsupported document type: {suffix}")

    def _extract_pdf(self, path: Path) -> dict[str, Any]:
        import fitz

        doc = fitz.open(path)
        try:
            pages = [page.get_text("text") or "" for page in doc]
            text = "\n".join(pages).strip()
            return {
                "document_path": str(path.resolve()),
                "page_count": int(doc.page_count),
                "text": text,
                "ocr_quality": _score_ocr_quality(text),
            }
        finally:
            doc.close()

    def _extract_docx(self, path: Path) -> dict[str, Any]:
        from docx import Document

        document = Document(str(path))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs).strip()
        return {
            "document_path": str(path.resolve()),
            "page_count": max(1, len(paragraphs) // 20),
            "text": text,
            "ocr_quality": _score_ocr_quality(text),
        }

    async def health_check(self) -> dict[str, str]:
        try:
            import fitz  # noqa: F401
            from docx import Document  # noqa: F401

            return {"document_extractor": "ok"}
        except Exception as exc:
            return {"document_extractor": "error", "reason": unwrap_retry_error(exc)}

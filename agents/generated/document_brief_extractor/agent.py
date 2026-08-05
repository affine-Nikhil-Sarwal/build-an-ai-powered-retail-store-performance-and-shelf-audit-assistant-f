"""Document Brief Extractor — PDF/DOCX extraction and prior findings summary."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient
from integrations.document_extractor import DocumentExtractor

_SYSTEM = (
    "Summarize prior audit findings from report text. Return JSON with keys: "
    "prior_findings (list of {category, description, severity, report_excerpt, page_ref}), "
    "summary (string), metadata ({store_area, audit_date}). "
    "Ground every finding in provided text only."
)


def _empty_findings(note: str) -> dict[str, Any]:
    return {
        "document_id": "",
        "extracted_text": "",
        "ocr_quality": "poor",
        "prior_findings": [],
        "summary": note,
        "metadata": {"store_area": None, "audit_date": None},
        "extraction_error": note,
    }


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    if payload.get("run_document_path") is False:
        return {
            "report_findings": {
                "document_id": "",
                "extracted_text": "",
                "ocr_quality": "good",
                "prior_findings": [],
                "summary": "Document path skipped by router",
                "metadata": {"store_area": None, "audit_date": None},
            }
        }

    package = payload.get("validated_upload_package") or {}
    doc_paths = package.get("document_paths") or []
    if not doc_paths:
        return {"report_findings": _empty_findings("No document provided")}

    extractor = DocumentExtractor()
    doc_path = doc_paths[0]
    try:
        extracted = extractor.extract(doc_path)
    except Exception as exc:
        return {"report_findings": _empty_findings(str(exc))}

    text = extracted.get("text") or ""
    ocr_quality = extracted.get("ocr_quality") or "partial"
    prior_findings: list[dict[str, Any]] = []
    summary = ""
    metadata = {"store_area": None, "audit_date": None}

    if dry_run or ocr_quality == "poor":
        if text:
            summary = text[:500]
            prior_findings = [
                {
                    "category": "report_context",
                    "description": "Extracted report excerpt (dry-run or poor OCR)",
                    "severity": "medium",
                    "report_excerpt": text[:240],
                    "page_ref": 1,
                }
            ]
    else:
        llm = AzureOpenAIClient(settings)
        parsed = llm.chat_json(
            system=_SYSTEM,
            user=f"Report text:\n{text[:12000]}",
            max_tokens=1400,
        )
        prior_findings = list(parsed.get("prior_findings") or [])
        summary = str(parsed.get("summary") or "")
        metadata = dict(parsed.get("metadata") or metadata)

    return {
        "report_findings": {
            "document_id": doc_path,
            "extracted_text": text,
            "ocr_quality": ocr_quality,
            "prior_findings": prior_findings,
            "summary": summary,
            "metadata": metadata,
        }
    }

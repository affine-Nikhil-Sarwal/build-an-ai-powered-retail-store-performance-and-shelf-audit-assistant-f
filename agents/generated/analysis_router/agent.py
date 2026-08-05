"""Analysis Router — LLM classification with modality-aware fallback."""

from __future__ import annotations

import re
from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient

ALLOWED_TYPES = ("vision_then_unified", "unified_only", "vision_only")


def _heuristic_route(has_document: bool, has_image: bool) -> tuple[str, bool, bool, str]:
    if has_document and has_image:
        return "vision_then_unified", True, True, "Both document and images present (heuristic)"
    if has_document:
        return "unified_only", True, False, "Document only (heuristic)"
    if has_image:
        return "vision_only", False, True, "Images only (heuristic)"
    return "unified_only", False, False, "No modalities detected (heuristic)"


def _llm_classify(
    *,
    llm: AzureOpenAIClient,
    has_document: bool,
    has_image: bool,
) -> str | None:
    system = (
        "Classify retail audit routing. Return JSON {\"analysis_type\": one of "
        + ", ".join(ALLOWED_TYPES)
        + "}. Prefer vision_then_unified when both report and shelf photos exist."
    )
    user = f"has_document={has_document}, has_image={has_image}"
    parsed = llm.chat_json(system=system, user=user, max_tokens=120)
    label = str(parsed.get("analysis_type") or "").strip()
    if label in ALLOWED_TYPES:
        return label
    return None


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    package = payload.get("validated_upload_package") or {}
    doc_paths = package.get("document_paths") or payload.get("document_paths") or []
    image_paths = package.get("image_paths") or payload.get("image_paths") or []
    has_document = bool(doc_paths or payload.get("documents_pdf_docx"))
    has_image = bool(image_paths or payload.get("one_or_more_current_retail_shelf_photos"))

    analysis_type: str | None = None
    reason = ""
    run_document = False
    run_vision = False

    if dry_run:
        analysis_type, run_document, run_vision, reason = _heuristic_route(has_document, has_image)
    else:
        try:
            llm = AzureOpenAIClient(settings)
            analysis_type = _llm_classify(llm=llm, has_document=has_document, has_image=has_image)
        except Exception as exc:
            reason = f"LLM classification failed: {exc}"
        if not analysis_type:
            analysis_type, run_document, run_vision, reason = _heuristic_route(has_document, has_image)
        else:
            run_document = analysis_type in ("vision_then_unified", "unified_only")
            run_vision = analysis_type in ("vision_then_unified", "vision_only")
            reason = reason or f"LLM selected {analysis_type}"

    if has_image and not run_vision:
        analysis_type = "vision_then_unified" if has_document else "vision_only"
        run_vision = True
        if has_document:
            run_document = True
        reason = f"{reason}; forced vision-inclusive route because images are present"

    if analysis_type is None:
        analysis_type, run_document, run_vision, reason = _heuristic_route(has_document, has_image)

    return {
        "analysis_type": analysis_type,
        "run_document_path": run_document,
        "run_vision_path": run_vision,
        "reason": reason,
        "validated_upload_package": package,
        "activate_image": run_vision,
        "route_to_image_path": run_vision,
    }

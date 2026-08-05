"""Evidence Confidence Check — groundedness and synthesis gate."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient

_SEVERITY_WEIGHT = {"critical": 1.0, "high": 0.85, "medium": 0.6, "low": 0.35}


def _deterministic_score(issue: dict[str, Any], ocr_quality: str | None) -> dict[str, Any]:
    refs = issue.get("evidence_refs") or []
    photo_refs = [r for r in refs if r.get("type") == "photo"]
    report_refs = [r for r in refs if r.get("type") == "report_excerpt"]
    severity = str(issue.get("severity") or "medium").lower()
    base = _SEVERITY_WEIGHT.get(severity, 0.5)
    if photo_refs:
        base = min(1.0, base + 0.25)
    if report_refs:
        base = min(1.0, base + 0.1)
    if issue.get("conflict_flags"):
        base *= 0.85
    if ocr_quality == "poor":
        base *= 0.6
    elif ocr_quality == "partial":
        base *= 0.8
    insufficient = base < 0.35 or (not photo_refs and not report_refs)
    return {
        "confidence": round(max(0.0, min(1.0, base)), 3),
        "groundedness": round(min(1.0, len(refs) * 0.35), 3),
        "completeness": round(min(1.0, 0.5 + len(photo_refs) * 0.2), 3),
        "conflict_detected": bool(issue.get("conflict_flags")),
        "insufficient_evidence": insufficient,
        "ready_for_synthesis": not insufficient,
        "evidence_strength": "photo" if photo_refs else "report" if report_refs else "none",
        "feedback": "Scored from available evidence refs",
    }


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    merged = payload.get("merged_evidence_set") or {}
    issues = list(merged.get("issues") or [])
    ocr_quality = payload.get("ocr_quality")
    scored: list[dict[str, Any]] = []
    for issue in issues:
        metrics = _deterministic_score(issue, ocr_quality)
        if not dry_run and metrics["ready_for_synthesis"]:
            try:
                llm = AzureOpenAIClient(settings)
                parsed = llm.chat_json(
                    system="Score issue confidence 0-1. Return JSON {confidence, feedback}.",
                    user=str({k: issue.get(k) for k in ("category", "description", "source", "severity")}),
                    max_tokens=200,
                )
                llm_conf = float(parsed.get("confidence") or metrics["confidence"])
                metrics["confidence"] = round(max(metrics["confidence"] * 0.7, min(1.0, llm_conf)), 3)
                metrics["feedback"] = str(parsed.get("feedback") or metrics["feedback"])
            except Exception as exc:
                metrics["feedback"] = f"{metrics['feedback']}; LLM assist skipped: {exc}"
        scored.append({**issue, **metrics})

    any_ready = any(item.get("ready_for_synthesis") for item in scored)
    return {
        "scored_issues": {
            "issues": scored,
            "ready_for_synthesis": any_ready,
            "feedback": "Evidence check complete before synthesis",
        }
    }

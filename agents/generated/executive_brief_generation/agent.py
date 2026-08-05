"""Executive Brief Generation — one-page narrative grounded in prioritized issues."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient


def _dry_run_brief(prioritized: list[dict[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any]:
    if not prioritized:
        summary = (
            "Insufficient evidence to produce a shelf audit brief. "
            "Retake clearer shelf photos and supply a readable audit report."
        )
        return {
            "title": "Shelf Audit — Insufficient Evidence",
            "executive_summary": summary,
            "key_findings": ["No prioritized issues met evidence thresholds"],
            "confidence_disclaimer": "Analysis ran in dry-run or lacked sufficient evidence.",
            "word_count": len(summary.split()),
        }
    bullets = [f"{p.get('category')}: {p.get('description')}" for p in prioritized[:5]]
    summary = " ".join(
        [
            "Executive shelf audit summary.",
            f"Top issue: {prioritized[0].get('description')}.",
            f"{len(prioritized)} prioritized findings require manager attention.",
        ]
    )
    return {
        "title": "Retail Shelf Audit Executive Brief",
        "executive_summary": summary,
        "key_findings": bullets,
        "confidence_disclaimer": "Grounded in uploaded evidence only.",
        "word_count": len(summary.split()),
    }


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    prioritized = list(payload.get("prioritized_issues") or [])
    actions = list(payload.get("actions") or [])

    if dry_run:
        brief = _dry_run_brief(prioritized, actions)
        recommendations = [
            {
                "issue_id": a.get("issue_id"),
                "recommendation": a.get("action_text"),
            }
            for a in actions
        ]
        return {"brief_draft": brief, "recommendations": recommendations}

    llm = AzureOpenAIClient(settings)
    parsed = llm.chat_json(
        system=(
            "Write a one-page executive brief. Return JSON {title, executive_summary, key_findings, "
            "confidence_disclaimer, word_count}. Do not invent facts beyond prioritized issues."
        ),
        user=str({"prioritized_issues": prioritized, "actions": actions}),
        max_tokens=1400,
    )
    brief = {
        "title": parsed.get("title") or "Shelf Audit Brief",
        "executive_summary": parsed.get("executive_summary") or "",
        "key_findings": list(parsed.get("key_findings") or []),
        "confidence_disclaimer": parsed.get("confidence_disclaimer") or "",
        "word_count": int(parsed.get("word_count") or 0),
    }
    recommendations = [
        {
            "issue_id": a.get("issue_id"),
            "recommendation": a.get("action_text"),
        }
        for a in actions
    ]
    return {"brief_draft": brief, "recommendations": recommendations}

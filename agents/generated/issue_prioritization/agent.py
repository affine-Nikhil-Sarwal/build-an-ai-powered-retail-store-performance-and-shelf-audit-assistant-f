"""Issue Prioritization — deterministic ranking with advisory actions."""

from __future__ import annotations

from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient

_SEVERITY_SCORE = {"critical": 100, "high": 80, "medium": 55, "low": 30}


def _priority_band(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    scored = payload.get("scored_issues") or {}
    issues = list(scored.get("issues") or [])
    ranked: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    for issue in issues:
        if issue.get("insufficient_evidence"):
            continue
        severity = str(issue.get("severity") or "medium").lower()
        score = float(_SEVERITY_SCORE.get(severity, 50))
        if issue.get("evidence_strength") == "photo":
            score += 20
        if issue.get("source") == "both":
            score += 10
        score *= float(issue.get("confidence") or 0.5)
        score = round(score, 2)
        band = _priority_band(score)
        rationale = (
            f"Severity={severity}, confidence={issue.get('confidence')}, "
            f"evidence={issue.get('evidence_strength')}"
        )
        if not dry_run:
            try:
                llm = AzureOpenAIClient(settings)
                parsed = llm.chat_json(
                    system="Return JSON {rationale} — one sentence grounded in issue fields only.",
                    user=str(issue.get("description") or ""),
                    max_tokens=120,
                )
                rationale = str(parsed.get("rationale") or rationale)
            except Exception:
                pass
        ranked.append(
            {
                **issue,
                "priority_score": score,
                "priority_band": band,
                "rationale": rationale,
            }
        )
        actions.append(
            {
                "issue_id": issue.get("issue_id"),
                "action_text": f"Review and correct {issue.get('category')}: {issue.get('description')}",
                "urgency": band,
                "owner_hint": "store_manager",
            }
        )

    ranked.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    for idx, item in enumerate(ranked, start=1):
        item["rank"] = idx

    return {"prioritized_issues": ranked, "actions": actions}

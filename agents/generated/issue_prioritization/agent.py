"""Issue Prioritization — deterministic ranking with advisory actions."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from config.settings import Settings
from integrations.azure_openai import AzureOpenAIClient

_SEVERITY_SCORE = {"critical": 100, "high": 80, "medium": 55, "low": 30}


def report_artifact_basename(job_id: str) -> str:
    return f"audit_report_{job_id}"


def findings_csv_fieldnames(findings: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        for key in finding:
            if key not in seen:
                seen.add(key)
                names.append(key)
    return names


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def serialize_findings_csv(findings: list[dict[str, Any]]) -> str:
    fieldnames = findings_csv_fieldnames(findings)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for finding in findings:
        writer.writerow({key: _csv_cell(finding.get(key)) for key in fieldnames})
    return output.getvalue()


def write_findings_csv(findings: list[dict[str, Any]], path: str | Path) -> str:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(serialize_findings_csv(findings), encoding="utf-8")
    return str(dest.resolve())


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

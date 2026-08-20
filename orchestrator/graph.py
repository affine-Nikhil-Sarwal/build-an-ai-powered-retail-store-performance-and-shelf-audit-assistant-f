"""Workflow graph orchestration."""

from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from config.autogen_azure_compat import apply_autogen_azure_compat
from config.settings import get_settings
from utils.json_safe import json_safe

from agents.adapters.drilldown_adapter import build_drilldown_input
from agents.adapters.vision_input_adapter import build_vision_input

ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = ROOT / "workflow_manifest.json"

_NODE_ENTRYPOINTS: dict[str, str] = {
    "upload-intake": "agents.generated.upload_intake.agent:run",
    "analysis-router": "agents.generated.analysis_router.agent:run",
    "document-brief-extractor": "agents.generated.document_brief_extractor.agent:run",
    "shelf-image-quality-gate": "agents.generated.shelf_image_quality_gate.agent:run",
    "shelf-row-detection": "agents.generated.shelf_row_detection.agent:run",
    "shelf-vision-analysis": "agents.generated.shelf_vision_analysis.agent:run",
    "evidence-merge-gate": "agents.generated.evidence_merge_gate.agent:run",
    "evidence-confidence-check": "agents.generated.evidence_confidence_check.agent:run",
    "issue-prioritization": "agents.generated.issue_prioritization.agent:run",
    "executive-brief-generation": "agents.generated.executive_brief_generation.agent:run",
    "manager-drilldown-output": "agents.generated.manager_drilldown_output.agent:run",
}

_EXECUTION_ORDER = list(_NODE_ENTRYPOINTS.keys())


def _load_runner(entrypoint: str) -> Callable[..., dict[str, Any]]:
    module_name, func_name = entrypoint.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def _invoke(node_id: str, payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    apply_autogen_azure_compat()
    settings = get_settings(dry_run=dry_run)
    runner = _load_runner(_NODE_ENTRYPOINTS[node_id])
    return runner(payload, settings=settings, dry_run=dry_run)


def run_workflow_from_node(node_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute the retail shelf audit workflow from ``node_id`` through terminal output."""
    data = dict(payload or {})
    dry_run = bool(data.pop("dry_run", False))
    state: dict[str, Any] = dict(data)

    if node_id == "upload-intake" or "validated_upload_package" not in state:
        intake_out = _invoke("upload-intake", state, dry_run=dry_run)
        state.update(intake_out)

    if node_id in ("upload-intake", "analysis-router") or node_id not in _NODE_ENTRYPOINTS:
        router_out = _invoke("analysis-router", state, dry_run=dry_run)
        state.update(router_out)
    else:
        router_out = {
            "run_document_path": state.get("run_document_path", True),
            "run_vision_path": state.get("run_vision_path", True),
            "analysis_type": state.get("analysis_type", "vision_then_unified"),
        }

    run_document = router_out.get("run_document_path", True)
    run_vision = router_out.get("run_vision_path", True)

    def _doc_branch() -> dict[str, Any]:
        if not run_document:
            return {}
        return _invoke(
            "document-brief-extractor",
            {**state, "run_document_path": True},
            dry_run=dry_run,
        )

    def _vision_branch() -> dict[str, Any]:
        if not run_vision:
            return {
                "usable_shelf_images": {
                    "images": [],
                    "rejected_images": [],
                    "overall_usable_count": 0,
                }
            }
        quality_out = _invoke(
            "shelf-image-quality-gate",
            {**state, "run_vision_path": True},
            dry_run=dry_run,
        )
        row_out = _invoke("shelf-row-detection", {**state, **quality_out}, dry_run=dry_run)
        vision_in = build_vision_input(
            detected_rows=row_out.get("detected_rows"),
            products=row_out.get("products"),
        )
        vision_out = _invoke(
            "shelf-vision-analysis",
            {**state, **vision_in},
            dry_run=dry_run,
        )
        return {**quality_out, **row_out, **vision_out}

    with ThreadPoolExecutor(max_workers=2) as pool:
        doc_out = pool.submit(_doc_branch).result()
        vision_out = pool.submit(_vision_branch).result()
    state.update(doc_out)
    state.update(vision_out)

    merge_out = _invoke("evidence-merge-gate", {**state, **doc_out, **vision_out}, dry_run=dry_run)
    state.update(merge_out)

    ocr_quality = None
    report = state.get("report_findings")
    if isinstance(report, dict):
        ocr_quality = report.get("ocr_quality")

    confidence_out = _invoke(
        "evidence-confidence-check",
        {**state, **merge_out, "ocr_quality": ocr_quality},
        dry_run=dry_run,
    )
    state.update(confidence_out)

    priority_out = _invoke("issue-prioritization", {**state, **confidence_out}, dry_run=dry_run)
    state.update(priority_out)

    brief_out = _invoke("executive-brief-generation", {**state, **priority_out}, dry_run=dry_run)
    state.update(brief_out)

    workflow_context = {
        "prioritized_issues": priority_out.get("prioritized_issues"),
        "scored_issues": confidence_out.get("scored_issues"),
        "merged_evidence_set": merge_out.get("merged_evidence_set"),
        "validated_upload_package": state.get("validated_upload_package"),
        "usable_shelf_images": state.get("usable_shelf_images"),
    }
    drill_in = build_drilldown_input(
        brief_draft=brief_out.get("brief_draft") or {},
        recommendations=brief_out.get("recommendations") or [],
        workflow_context=workflow_context,
    )
    final_out = _invoke("manager-drilldown-output", {**state, **drill_in}, dry_run=dry_run)
    state.update(final_out)
    return json_safe(state)


def write_manifest() -> None:
    manifest = {
        "nodes": _EXECUTION_ORDER,
        "execution_order": _EXECUTION_ORDER,
        "entrypoints": _NODE_ENTRYPOINTS,
        "step_count": len(_EXECUTION_ORDER),
    }
    _MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

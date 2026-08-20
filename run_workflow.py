"""Graph execution entrypoint — delegates to orchestrator.graph."""

from __future__ import annotations

from typing import Any

try:
    from config.autogen_azure_compat import apply_autogen_azure_compat

    apply_autogen_azure_compat()
except Exception:
    pass

from orchestrator.graph import run_workflow_from_node as _run_workflow_from_node
from utils.json_safe import json_safe


def _normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    raw_images = data.get("image_paths")
    if raw_images is None:
        raw_images = data.get("one_or_more_current_retail_shelf_photos")
    if isinstance(raw_images, str):
        data["image_paths"] = [raw_images]
    elif raw_images is not None and not isinstance(raw_images, list):
        data["image_paths"] = list(raw_images)
    elif isinstance(raw_images, list):
        data["image_paths"] = raw_images
    return data


def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the full workflow from upload intake."""
    return run_workflow_from_node("upload-intake", payload)


def run_workflow_from_node(node_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the workflow graph starting at ``node_id`` and return JSON-safe output."""
    return json_safe(_run_workflow_from_node(node_id, _normalize_payload(payload)))

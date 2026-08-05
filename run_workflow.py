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


def run_workflow(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the full workflow from upload intake."""
    return run_workflow_from_node("upload-intake", payload)


def run_workflow_from_node(node_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the workflow graph starting at ``node_id`` and return JSON-safe output."""
    return json_safe(_run_workflow_from_node(node_id, payload))

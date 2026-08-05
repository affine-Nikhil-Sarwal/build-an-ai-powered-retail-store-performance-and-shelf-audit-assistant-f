"""Backward-compatible re-export of orchestrator.graph.run_workflow_from_node."""

from orchestrator.graph import run_workflow_from_node, write_manifest
from utils.json_safe import json_safe

__all__ = ["run_workflow_from_node", "write_manifest", "_json_safe"]

_json_safe = json_safe

if __name__ == "__main__":
    write_manifest()

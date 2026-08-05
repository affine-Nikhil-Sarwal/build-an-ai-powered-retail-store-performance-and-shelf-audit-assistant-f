"""Graph execution entrypoint — the cloud agent implements node wiring here."""

from __future__ import annotations

from typing import Any

# Idempotent: honor AZURE_OPENAI_DEPLOYMENT (incl. dotted names) for ag2 create/cost.
try:
    from config.autogen_azure_compat import apply_autogen_azure_compat

    apply_autogen_azure_compat()
except Exception:
    pass


def _json_safe(value: Any) -> Any:
    """Recursively drop bytes/bytearray so FastAPI JSON responses never see raw binary."""
    if isinstance(value, (bytes, bytearray)):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items() if not isinstance(v, (bytes, bytearray))}
    if isinstance(value, list):
        return [_json_safe(v) for v in value if not isinstance(v, (bytes, bytearray))]
    if isinstance(value, tuple):
        return tuple(_json_safe(v) for v in value if not isinstance(v, (bytes, bytearray)))
    return value


def run_workflow_from_node(node_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the workflow graph starting at ``node_id`` and return the terminal output.

    Implementations MUST return ``_json_safe(result)`` so raw upload bytes never
    reach the HTTP response (see generate_project BINARY / FILE PAYLOAD SAFETY).
    """
    raise NotImplementedError(
        "Implement graph execution in run_workflow.py (discover agents, wire adapters, invoke entrypoints)."
    )

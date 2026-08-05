"""Integration tests for workflow wiring, config, HTTP, and dry-run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.settings import ConfigurationError, get_settings
from main import app
from orchestrator.graph import _EXECUTION_ORDER, _NODE_ENTRYPOINTS, run_workflow_from_node, write_manifest
from utils.json_safe import json_safe


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def test_discover_generated_agents():
    generated = ROOT / "agents" / "generated"
    dirs = [p.name for p in generated.iterdir() if p.is_dir()]
    assert "upload_intake" in dirs
    assert "analysis_router" in dirs
    for node_id, entry in _NODE_ENTRYPOINTS.items():
        module_path = entry.split(":")[0].replace(".", "/") + ".py"
        assert (ROOT / module_path).is_file(), f"missing {module_path} for {node_id}"


def test_manifest_step_count_matches_graph():
    write_manifest()
    manifest = json.loads((ROOT / "workflow_manifest.json").read_text(encoding="utf-8"))
    assert manifest["step_count"] == len(_EXECUTION_ORDER)
    assert len(manifest["nodes"]) == 12


def test_config_raises_configuration_error_when_live_vars_missing(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError):
        get_settings(dry_run=False)


def test_dry_run_workflow_exits_successfully():
    result = run_workflow_from_node(
        "upload-intake",
        {
            "dry_run": True,
            "document_paths": [str(EXAMPLES / "sample_audit.pdf")],
            "image_paths": [str(EXAMPLES / "sample_shelf.jpg")],
        },
    )
    assert result.get("validated_upload_package")
    assert result.get("one_page_narrative_executive_brief")
    assert "prioritized_issue_list" in result


def test_json_safe_strips_bytes():
    payload = {"a": b"secret", "b": {"c": bytearray(b"x")}, "ok": 1}
    cleaned = json_safe(payload)
    assert "a" not in cleaned or cleaned.get("a") is None
    assert cleaned["ok"] == 1


def test_analysis_router_forces_vision_with_image_no_keywords():
    from agents.generated.analysis_router.agent import run

    settings = get_settings(dry_run=True)
    out = run(
        {
            "validated_upload_package": {
                "document_paths": ["/tmp/report.pdf"],
                "image_paths": ["/tmp/shelf.jpg"],
            }
        },
        settings=settings,
        dry_run=True,
    )
    assert out["run_vision_path"] is True
    assert out["analysis_type"] in ("vision_then_unified", "vision_only")


def test_upload_intake_execute_real_validation():
    from agents.generated.upload_intake.agent import run

    settings = get_settings(dry_run=True)
    out = run(
        {
            "document_paths": [str(EXAMPLES / "sample_audit.pdf")],
            "image_paths": [str(EXAMPLES / "sample_shelf.jpg")],
        },
        settings=settings,
        dry_run=True,
    )
    package = out["validated_upload_package"]
    assert package["policy_check_passed"] is True
    assert package["document_paths"]
    assert package["image_paths"]


def test_http_intake_and_health_include_request_id(monkeypatch):
    get_settings.cache_clear()
    settings = get_settings(dry_run=True)
    monkeypatch.setattr("api.routes.get_settings", lambda dry_run=False: settings)

    def _run(node_id, payload=None):
        data = dict(payload or {})
        data["dry_run"] = True
        return run_workflow_from_node(node_id, data)

    monkeypatch.setattr("api.routes.run_workflow_from_node", _run)

    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code in (200, 503)
    assert health.headers.get("X-Request-ID")
    assert health.json().get("integrations") is not None

    with open(EXAMPLES / "sample_audit.pdf", "rb") as doc, open(
        EXAMPLES / "sample_shelf.jpg", "rb"
    ) as img:
        response = client.post(
            "/audit/intake",
            files={
                "report": ("sample_audit.pdf", doc, "application/pdf"),
                "shelf_photos": ("sample_shelf.jpg", img, "image/jpeg"),
            },
        )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    body = response.json()
    assert body.get("one_page_narrative_executive_brief")

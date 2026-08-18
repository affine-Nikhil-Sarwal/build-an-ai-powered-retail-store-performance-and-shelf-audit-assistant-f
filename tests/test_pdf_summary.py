"""Tests for audit summary PDF generation and delivery."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from config.settings import get_settings
from integrations.audit_summary_pdf import build_audit_summary_pdf
from main import app
from orchestrator.graph import run_workflow_from_node
from utils.pdf_delivery import attach_pdf_download_if_ready, pdf_report_path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture
def sample_audit_result(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path / "uploads"))
    settings = get_settings(dry_run=True)
    result = run_workflow_from_node(
        "upload-intake",
        {
            "dry_run": True,
            "document_paths": [str(EXAMPLES / "sample_audit.pdf")],
            "image_paths": [str(EXAMPLES / "sample_shelf.jpg")],
        },
    )
    return result, settings


def test_build_audit_summary_pdf_writes_expected_sections(sample_audit_result, tmp_path):
    result, _settings = sample_audit_result
    output_path = tmp_path / "audit_summary.pdf"
    build_audit_summary_pdf(result, output_path)

    assert output_path.is_file()
    doc = fitz.open(output_path)
    text = "".join(page.get_text() for page in doc)
    doc.close()

    assert "Retail Shelf Audit Summary Report" in text
    assert "Executive Summary" in text
    assert "Prioritized Issues" in text
    assert "Recommended Corrective Actions" in text
    assert "Confidence Notes" in text


def test_attach_pdf_download_if_ready_includes_link_when_fast(sample_audit_result):
    result, settings = sample_audit_result
    enriched = attach_pdf_download_if_ready(
        result,
        settings=settings,
        timeout_seconds=5.0,
        base_url="http://testserver",
    )

    assert "pdf_summary_report" in enriched
    report = enriched["pdf_summary_report"]
    assert report["download_url"].startswith("http://testserver/audit/reports/")
    assert report["download_url"].endswith("/summary.pdf")
    assert Path(report["path"]).is_file()


def test_attach_pdf_download_if_ready_omits_link_on_timeout(sample_audit_result, monkeypatch):
    result, settings = sample_audit_result

    def _slow_generate(*_args, **_kwargs):
        import time

        time.sleep(0.2)
        return None

    monkeypatch.setattr("utils.pdf_delivery._generate_pdf_safe", _slow_generate)
    enriched = attach_pdf_download_if_ready(
        result,
        settings=settings,
        timeout_seconds=0.01,
    )
    assert "pdf_summary_report" not in enriched


def test_http_download_audit_summary_pdf(sample_audit_result, monkeypatch):
    result, settings = sample_audit_result
    job_id = result["validated_upload_package"]["job_id"]
    report_path = pdf_report_path(settings, job_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    build_audit_summary_pdf(result, report_path)

    get_settings.cache_clear()
    monkeypatch.setattr("api.routes.get_settings", lambda dry_run=False: settings)

    client = TestClient(app)
    response = client.get(f"/audit/reports/{job_id}/summary.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

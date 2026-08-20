"""Intake routes and health checks for the retail shelf audit workflow."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config.settings import get_settings
from integrations.azure_openai import AzureOpenAIClient
from integrations.document_extractor import DocumentExtractor
from integrations.local_storage import LocalStorageClient
from integrations.policy_validator import PolicyValidator
from integrations.row_detector import RowDetector
from integrations.vision_quality import VisionQualityChecker
from orchestrator.graph import run_workflow_from_node

router = APIRouter()


def _integration_unhealthy(name: str, info: dict[str, Any]) -> str | None:
    for key, value in info.items():
        if value == "error":
            reason = info.get("reason", "unhealthy")
            return f"{name}: {reason}"
    return None


async def _collect_health(settings) -> tuple[dict[str, Any], list[str]]:
    storage = LocalStorageClient(settings)
    azure = AzureOpenAIClient(settings)
    doc = DocumentExtractor()
    policy = PolicyValidator()
    rows = RowDetector(settings)
    vision = VisionQualityChecker()
    results = await asyncio.gather(
        storage.health_check(),
        azure.health_check(),
        doc.health_check(),
        policy.health_check(),
        rows.health_check(),
        vision.health_check(),
    )
    integrations: dict[str, Any] = {}
    unhealthy: list[str] = []
    for item in results:
        integrations.update(item)
        for name, value in item.items():
            if value == "error":
                unhealthy.append(f"{name}: {item.get('reason', 'unhealthy')}")
    if settings.dry_run:
        unhealthy = [u for u in unhealthy if not u.startswith("azure_openai")]
    return integrations, unhealthy


@router.get("/health", tags=["health"], summary="Integration health")
async def health() -> Any:
    settings = get_settings(dry_run=False)
    try:
        integrations, unhealthy = await _collect_health(settings)
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "reason": str(exc), "integrations": {}},
        )
    body = {"status": "ok" if not unhealthy else "degraded", "integrations": integrations}
    if unhealthy:
        body["unhealthy"] = unhealthy
        return JSONResponse(status_code=503, content=body)
    return body


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name or "upload.bin").name).strip("._")
    return cleaned or "upload.bin"


async def _persist_upload(upload: UploadFile, suffix: str) -> str:
    import os

    original = _safe_filename(upload.filename or f"file{suffix}")
    fd, tmp_path = tempfile.mkstemp(suffix=Path(original).suffix or suffix)
    os.close(fd)
    dest = Path(tmp_path)
    content = await upload.read()
    dest.write_bytes(content)
    return str(dest.resolve())


@router.post("/audit/intake", tags=["intake"], summary="Upload report and shelf photos")
async def audit_intake(
    report: UploadFile = File(...),
    shelf_photos: list[UploadFile] = File(...),
) -> dict[str, Any]:
    """Accept audit report (PDF/DOCX) and one or more shelf photos, then run the workflow."""
    uploads = shelf_photos if isinstance(shelf_photos, list) else [shelf_photos]
    if not uploads:
        raise HTTPException(status_code=422, detail="At least one shelf photo is required")

    report_path = await _persist_upload(report, ".pdf")
    image_paths = [await _persist_upload(photo, ".jpg") for photo in uploads]

    payload = {
        "document_paths": [report_path],
        "image_paths": image_paths,
    }
    return await asyncio.to_thread(run_workflow_from_node, "upload-intake", payload)

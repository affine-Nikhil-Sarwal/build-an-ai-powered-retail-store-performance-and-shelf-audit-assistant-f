"""HTTP routes for retail shelf audit intake and health."""

from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config.settings import get_settings
from orchestrator.graph import run_workflow_from_node

APP_ROOT = Path(__file__).resolve().parent.parent
router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    from main import _integration_health

    report = await _integration_health(dry_run=False)
    status_code = 200 if report.get("status") == "ok" else 503
    if report.get("failures"):
        report["reason"] = "; ".join(report["failures"])
    return JSONResponse(status_code=status_code, content=report)


@router.post("/audit/intake", tags=["intake"])
async def audit_intake(
    report: UploadFile = File(...),
    shelf_photos: list[UploadFile] = File(...),
) -> dict[str, Any]:
    """Multipart intake: one audit report plus one or more shelf photos."""
    if not shelf_photos:
        raise HTTPException(status_code=422, detail="At least one shelf photo is required")

    settings = get_settings(dry_run=False)
    uploads = settings.upload_path() / "http"
    uploads.mkdir(parents=True, exist_ok=True)

    def _save(upload: UploadFile, prefix: str) -> str:
        original = upload.filename or "upload.bin"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original).name).strip("._") or "upload.bin"
        dest = uploads / f"{prefix}-{uuid.uuid4().hex}-{safe}"
        with dest.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        return str(dest.resolve())

    document_path = _save(report, "report")
    image_paths = [_save(photo, "shelf") for photo in shelf_photos]

    payload = {
        "document_paths": [document_path],
        "image_paths": image_paths,
    }
    return await asyncio.to_thread(run_workflow_from_node, "upload-intake", payload)

"""Intake routes for the generated workflow — included by main.py."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field

from run_workflow import run_workflow_from_node

APP_ROOT = Path(__file__).resolve().parent.parent
router = APIRouter()


class WorkflowPayload(BaseModel):
    """JSON body accepted by intake endpoints."""

    data: dict[str, Any] = Field(default_factory=dict)

FILE_ROUTE_RUNTIME_DEPENDENCIES = ("python-multipart",)


@router.post("/upload", tags=["intake"], summary='Upload Intake')
async def upload_intake(file: UploadFile = File(...)) -> dict[str, Any]:
    """Start the workflow at node 'upload-intake' and return its result."""
    uploads_dir = APP_ROOT / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    original_name = file.filename or "upload.bin"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_name).name).strip("._")
    if not safe_name:
        safe_name = "upload.bin"
    saved_path = uploads_dir / f"upload-intake-{safe_name}"
    with saved_path.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)
    return run_workflow_from_node(
        'upload-intake',
        {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_path": str(saved_path),
        },
    )

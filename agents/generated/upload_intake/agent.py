"""Upload Intake — validate and persist report + shelf photos."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import Settings
from integrations.local_storage import LocalStorageClient
from integrations.policy_validator import PolicyValidator


def run(payload: dict[str, Any], *, settings: Settings, dry_run: bool = False) -> dict[str, Any]:
    document_paths = list(payload.get("document_paths") or [])
    if payload.get("documents_pdf_docx"):
        document_paths.append(payload["documents_pdf_docx"])
    image_paths = list(payload.get("image_paths") or payload.get("one_or_more_current_retail_shelf_photos") or [])
    if payload.get("file_path") and not document_paths and not image_paths:
        fp = payload["file_path"]
        if str(fp).lower().endswith((".pdf", ".docx")):
            document_paths = [fp]
        else:
            image_paths = [fp]

    if not document_paths:
        raise ValueError("At least one PDF or DOCX report document is required")
    if not image_paths:
        raise ValueError("At least one shelf photo is required")

    storage = LocalStorageClient(settings)
    policy = PolicyValidator()
    job_id = payload.get("job_id") or str(uuid.uuid4())
    job_id, job_dir = storage.create_job_dir(job_id)

    violations: list[str] = []
    persisted_docs: list[str] = []
    persisted_images: list[str] = []
    content_types: dict[str, str] = {}

    for idx, doc_path in enumerate(document_paths):
        violations.extend(policy.validate_document(doc_path))
        name = f"report_{idx + 1}{Path(doc_path).suffix.lower()}"
        saved = storage.persist_file(doc_path, job_dir / "documents", name)
        persisted_docs.append(saved)
        content_types[saved] = "application/pdf" if saved.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    for idx, img_path in enumerate(image_paths):
        violations.extend(policy.validate_image(img_path))
        name = f"shelf_{idx + 1}{Path(img_path).suffix.lower()}"
        saved = storage.persist_file(img_path, job_dir / "images", name)
        persisted_images.append(saved)
        content_types[saved] = f"image/{Path(saved).suffix.lstrip('.').lower()}"

    hard_fail = any("Disallowed" in v for v in violations)
    package = {
        "job_id": job_id,
        "document_paths": persisted_docs,
        "image_paths": persisted_images,
        "content_types": content_types,
        "storage_root": str(job_dir.resolve()),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "policy_check_passed": not hard_fail,
        "policy_violations": violations,
    }
    if hard_fail:
        raise ValueError("Policy validation failed: " + "; ".join(violations))
    return {"validated_upload_package": package}

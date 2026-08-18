"""Non-blocking PDF summary delivery for audit workflow responses."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from config.settings import Settings, get_settings
from integrations.audit_summary_pdf import generate_audit_summary_pdf

logger = logging.getLogger(__name__)

PDF_DOWNLOAD_ROUTE_TEMPLATE = "/audit/reports/{job_id}/summary.pdf"


def pdf_report_path(settings: Settings, job_id: str) -> Path:
    return settings.upload_path() / job_id / "reports" / "audit_summary.pdf"


def build_pdf_download_url(*, job_id: str, base_url: str | None = None) -> str:
    path = PDF_DOWNLOAD_ROUTE_TEMPLATE.format(job_id=job_id)
    if base_url:
        return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    return path


def _generate_pdf_safe(result: dict[str, Any], settings: Settings) -> Path | None:
    try:
        return generate_audit_summary_pdf(result, settings=settings)
    except Exception:
        logger.exception("audit_summary_pdf_generation_failed")
        return None


def attach_pdf_download_if_ready(
    result: dict[str, Any],
    *,
    settings: Settings | None = None,
    timeout_seconds: float | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Return a copy of ``result`` with a PDF download link when generation finishes in time."""
    package = result.get("validated_upload_package") or {}
    job_id = package.get("job_id")
    if not job_id:
        return result

    active_settings = settings or get_settings(dry_run=bool(result.get("dry_run")))
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else active_settings.pdf_generation_timeout_seconds
    )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_generate_pdf_safe, result, active_settings)
        try:
            pdf_path = future.result(timeout=timeout)
        except TimeoutError:
            logger.info("audit_summary_pdf_generation_slow job_id=%s timeout=%s", job_id, timeout)
            return result
        except Exception:
            logger.exception("audit_summary_pdf_generation_failed job_id=%s", job_id)
            return result

    if pdf_path is None or not pdf_path.is_file():
        return result

    enriched = dict(result)
    enriched["pdf_summary_report"] = {
        "job_id": str(job_id),
        "path": str(pdf_path),
        "download_url": build_pdf_download_url(job_id=str(job_id), base_url=base_url),
    }
    return enriched


async def attach_pdf_download_if_ready_async(
    result: dict[str, Any],
    *,
    settings: Settings | None = None,
    timeout_seconds: float | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Async wrapper that never blocks the response longer than ``timeout_seconds``."""
    package = result.get("validated_upload_package") or {}
    job_id = package.get("job_id")
    if not job_id:
        return result

    active_settings = settings or get_settings(dry_run=bool(result.get("dry_run")))
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else active_settings.pdf_generation_timeout_seconds
    )

    try:
        pdf_path = await asyncio.wait_for(
            asyncio.to_thread(_generate_pdf_safe, result, active_settings),
            timeout=timeout,
        )
    except TimeoutError:
        logger.info("audit_summary_pdf_generation_slow job_id=%s timeout=%s", job_id, timeout)
        return result
    except Exception:
        logger.exception("audit_summary_pdf_generation_failed job_id=%s", job_id)
        return result

    if pdf_path is None or not pdf_path.is_file():
        return result

    enriched = dict(result)
    enriched["pdf_summary_report"] = {
        "job_id": str(job_id),
        "path": str(pdf_path),
        "download_url": build_pdf_download_url(job_id=str(job_id), base_url=base_url),
    }
    return enriched

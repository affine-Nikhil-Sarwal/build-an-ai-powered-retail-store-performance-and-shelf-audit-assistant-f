"""CLI and FastAPI entrypoint for the Retail Shelf Audit Assistant."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from config.autogen_azure_compat import apply_autogen_azure_compat
from config.settings import ConfigurationError, get_settings
from orchestrator.graph import run_workflow_from_node, write_manifest

APP_ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


class RequestIdMiddleware:
    """Pure ASGI request-ID middleware."""

    header_name = b"x-request-id"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = b""
        for key, value in scope.get("headers") or []:
            if key.lower() == self.header_name:
                incoming = value
                break
        request_id = incoming.decode("latin-1").strip() or str(uuid.uuid4())
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((self.header_name, request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)


app = FastAPI(title="Retail Shelf Audit Assistant")
app.add_middleware(RequestIdMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Unhandled exception method=%s path=%s request_id=%s type=%s",
        request.method,
        request.url.path,
        request_id,
        type(exc).__name__,
    )
    headers: dict[str, str] = {}
    if request_id:
        headers["X-Request-ID"] = str(request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "request_id": request_id,
            "traceback": traceback.format_exc(),
        },
        headers=headers,
    )


from api.routes import router  # noqa: E402

app.include_router(router)


async def _integration_health(*, dry_run: bool) -> dict[str, Any]:
    from integrations.azure_openai import AzureOpenAIClient
    from integrations.document_extractor import DocumentExtractor
    from integrations.local_storage import LocalStorageClient
    from integrations.policy_validator import PolicyValidator
    from integrations.row_detector import RowDetector
    from integrations.vision_quality import VisionQualityChecker

    try:
        settings = get_settings(dry_run=dry_run)
    except ConfigurationError as exc:
        return {
            "status": "degraded",
            "integrations": {"configuration": "error", "reason": str(exc)},
            "failures": [str(exc)],
        }
    checks = await asyncio.gather(
        LocalStorageClient(settings).health_check(),
        DocumentExtractor().health_check(),
        AzureOpenAIClient(settings).health_check(),
        VisionQualityChecker().health_check(),
        RowDetector(settings).health_check(),
        PolicyValidator().health_check(),
    )
    merged: dict[str, Any] = {}
    for item in checks:
        merged.update(item)
    failures: list[str] = []
    for key, value in merged.items():
        if key in ("path", "mode", "deployment"):
            continue
        if key.endswith("_reason") or key == "reason":
            continue
        if value in ("ok", "skipped"):
            continue
        if isinstance(value, str) and "error" in value.lower():
            failures.append(f"{key}={value}")
    status = "ok" if not failures else "degraded"
    return {"status": status, "integrations": merged, "failures": failures}


def _collect_paths(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    docs: list[str] = []
    images: list[str] = []
    if args.file:
        for path in args.file:
            p = Path(path)
            if p.suffix.lower() in {".pdf", ".docx"}:
                docs.append(str(p.resolve()))
            else:
                images.append(str(p.resolve()))
    if args.document:
        docs.append(str(Path(args.document).resolve()))
    if args.image:
        images.extend(str(Path(p).resolve()) for p in args.image)
    if args.input_json:
        import json

        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        docs.extend(payload.get("document_paths") or [])
        images.extend(payload.get("image_paths") or [])
    return docs, images


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s request_id=%(request_id)s %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retail Shelf Audit Assistant")
    parser.add_argument("--health", action="store_true", help="Check integration health")
    parser.add_argument("--dry-run", action="store_true", help="Run workflow without live external calls")
    parser.add_argument("--file", action="append", help="Input file path (PDF/DOCX or image)")
    parser.add_argument("--document", help="Audit report PDF or DOCX path")
    parser.add_argument("--image", action="append", help="Shelf photo path")
    parser.add_argument("--input-json", help="JSON file with document_paths and image_paths")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI via uvicorn")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    _configure_logging()

    if args.serve:
        uvicorn.run("main:app", host=args.host, port=args.port, reload=False)
        return 0

    if args.health:
        dry = args.dry_run
        try:
            if not dry:
                settings = get_settings(dry_run=False)
                settings.export_to_environ()
                apply_autogen_azure_compat()
        except ConfigurationError as exc:
            print(f"configuration_error: {exc}", file=sys.stderr)
            return 1
        report = asyncio.run(_integration_health(dry_run=dry))
        print(report)
        return 0 if report.get("status") == "ok" or dry else 1

    if args.dry_run and not any([args.file, args.document, args.image, args.input_json]):
        write_manifest()
        result = run_workflow_from_node(
            "upload-intake",
            {
                "dry_run": True,
                "document_paths": [str(APP_ROOT / "examples" / "sample_audit.pdf")],
                "image_paths": [str(APP_ROOT / "examples" / "sample_shelf.jpg")],
            },
        )
        print({"dry_run": True, "job_id": (result.get("validated_upload_package") or {}).get("job_id")})
        return 0

    docs, images = _collect_paths(args)
    if not docs or not images:
        parser.error("Provide at least one document (--document/--file) and one image (--image/--file)")

    try:
        if not args.dry_run:
            settings = get_settings(dry_run=False)
            settings.export_to_environ()
            apply_autogen_azure_compat()
    except ConfigurationError as exc:
        print(f"configuration_error: {exc}", file=sys.stderr)
        return 1

    result = run_workflow_from_node(
        "upload-intake",
        {
            "dry_run": args.dry_run,
            "document_paths": docs,
            "image_paths": images,
        },
    )
    brief = result.get("one_page_narrative_executive_brief") or ""
    print(brief[:2000] if len(brief) > 2000 else brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

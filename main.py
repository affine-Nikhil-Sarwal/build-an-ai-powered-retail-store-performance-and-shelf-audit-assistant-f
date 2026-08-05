"""FastAPI HTTP surface and CLI for the Retail Shelf Audit Assistant."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.routes import router as api_router
from config.autogen_azure_compat import apply_autogen_azure_compat
from config.settings import ConfigurationError, get_settings
from orchestrator.graph import run_workflow_from_node

APP_ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

app = FastAPI(title="Retail Shelf Audit Assistant")


class RequestIdMiddleware:
    """Pure ASGI request-ID middleware — never BaseHTTPMiddleware."""

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
        logger.info("request_started request_id=%s path=%s", request_id, scope.get("path"))

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((self.header_name, request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)


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


app.include_router(api_router)


async def _cli_health(*, dry_run: bool) -> int:
    from api.routes import _collect_health

    settings = get_settings(dry_run=dry_run)
    integrations, unhealthy = await _collect_health(settings)
    print(json.dumps({"integrations": integrations, "unhealthy": unhealthy}, indent=2))
    return 0 if not unhealthy else 1


def _cli_dry_run(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {"dry_run": True}
    if args.input_json:
        payload.update(json.loads(Path(args.input_json).read_text(encoding="utf-8")))
    if args.file:
        payload.setdefault("document_paths", []).append(args.file)
    for image in args.image or []:
        payload.setdefault("image_paths", []).append(image)
    if not payload.get("document_paths") and EXAMPLES_PDF.exists():
        payload.setdefault("document_paths", [str(EXAMPLES_PDF)])
    if not payload.get("image_paths") and EXAMPLES_SHELF.exists():
        payload.setdefault("image_paths", [str(EXAMPLES_SHELF)])
    result = run_workflow_from_node("upload-intake", payload)
    print(json.dumps(result, indent=2, default=str))
    return 0


def _cli_run(args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {}
    if args.input_json:
        payload.update(json.loads(Path(args.input_json).read_text(encoding="utf-8")))
    if args.file:
        payload.setdefault("document_paths", []).append(args.file)
    for image in args.image or []:
        payload.setdefault("image_paths", []).append(image)
    if not payload.get("document_paths"):
        raise SystemExit("Provide --file with a PDF/DOCX report path")
    if not payload.get("image_paths"):
        raise SystemExit("Provide at least one --image shelf photo path")
    settings = get_settings(dry_run=False)
    settings.export_to_environ()
    apply_autogen_azure_compat()
    result = run_workflow_from_node("upload-intake", payload)
    print(json.dumps(result, indent=2, default=str))
    return 0


EXAMPLES_PDF = APP_ROOT / "examples" / "sample_audit.pdf"
EXAMPLES_SHELF = APP_ROOT / "examples" / "sample_shelf.jpg"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retail Store Performance and Shelf Audit Assistant",
    )
    parser.add_argument("--health", action="store_true", help="Check integration health and exit")
    parser.add_argument("--dry-run", action="store_true", help="Run full workflow without live external calls")
    parser.add_argument("--file", help="Path to audit report PDF or DOCX")
    parser.add_argument("--image", action="append", help="Path to shelf photo (repeatable)")
    parser.add_argument("--input-json", help="JSON file with document_paths and image_paths")
    parser.add_argument("--serve", action="store_true", help="Start uvicorn HTTP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.serve:
        import uvicorn

        uvicorn.run("main:app", host=args.host, port=args.port, reload=False)
        return 0

    if args.health:
        return asyncio.run(_cli_health(dry_run=args.dry_run))

    if args.dry_run:
        get_settings.cache_clear()
        return _cli_dry_run(args)

    if args.file or args.input_json or args.image:
        get_settings.cache_clear()
        try:
            return _cli_run(args)
        except ConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

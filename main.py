"""FastAPI HTTP surface for the generated workflow (scaffold)."""

from __future__ import annotations

import logging
import re
import shutil
import traceback
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from run_workflow import run_workflow_from_node
try:
    from config.autogen_azure_compat import apply_autogen_azure_compat

    apply_autogen_azure_compat()
except Exception:
    pass

APP_ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

app = FastAPI(title="Agentic LaunchPad Workflow")


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


class WorkflowPayload(BaseModel):
    """JSON body accepted by intake endpoints."""

    data: dict[str, Any] = Field(default_factory=dict)

from api.routes import router

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

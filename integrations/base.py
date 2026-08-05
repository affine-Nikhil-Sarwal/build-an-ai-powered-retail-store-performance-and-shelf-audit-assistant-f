"""Integration protocol helpers."""

from __future__ import annotations

from tenacity import RetryError


def unwrap_retry_error(exc: BaseException) -> str:
    if isinstance(exc, RetryError):
        last = exc.last_attempt
        if last is not None and last.failed:
            inner = last.exception()
            if inner is not None:
                return str(inner)
    return str(exc)

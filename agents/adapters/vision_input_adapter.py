"""Map shelf-row-detection outputs to shelf-vision-analysis inputs."""

from __future__ import annotations

from typing import Any

_DEFAULT_QUERY = (
    "Identify every visible product facing, stock-out, low facings, misplaced products, "
    "and empty shelf gaps. Scan the full row left-to-right and report any product regions "
    "that may have been missed by upstream detection. Only report what is visibly evident."
)


def build_vision_input(
    *,
    detected_rows: list[dict[str, Any]] | None,
    products: list[dict[str, Any]] | None,
    audit_query: str | None = None,
) -> dict[str, Any]:
    return {
        "detected_rows": detected_rows or [],
        "products": products or [],
        "audit_query": audit_query or _DEFAULT_QUERY,
    }

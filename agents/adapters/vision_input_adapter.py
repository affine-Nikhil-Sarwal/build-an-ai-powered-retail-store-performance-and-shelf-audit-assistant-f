"""Map shelf-row-detection outputs to shelf-vision-analysis inputs."""

from __future__ import annotations

from typing import Any

_DEFAULT_QUERY = (
    "Identify visible stock-outs, low facings, misplaced products, and empty shelf gaps. "
    "Only report what is visibly evident."
)


def build_vision_input(
    *,
    detected_rows: list[dict[str, Any]] | None,
    products: list[dict[str, Any]] | None,
    audit_query: str | None = None,
) -> dict[str, Any]:
    rows = list(detected_rows or [])
    product_regions = list(products or [])
    rows.sort(key=lambda row: (row.get("image_path", ""), row.get("row_index", 0)))
    product_regions.sort(
        key=lambda product: (product.get("image_path", ""), product.get("row_index", 0))
    )
    return {
        "detected_rows": rows,
        "products": product_regions,
        "audit_query": audit_query or _DEFAULT_QUERY,
    }

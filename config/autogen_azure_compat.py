"""Azure OpenAI + ag2 compatibility shims.

ag2 0.9 strips dots from Azure deployment names (``gpt-5.4`` -> ``gpt-54``) and
looks up ``response.model`` (often a dated snapshot like ``gpt-5.4-2026-03-05``)
in a static price table — producing noisy "model not found" cost warnings even
when the configured deployment is correct.

Apply once at process start (CLI / FastAPI). Idempotent.
"""

from __future__ import annotations

import logging
import os
from typing import Any

_applied = False
logger = logging.getLogger(__name__)


def _configured_deployment() -> str:
    return (
        os.environ.get("AZURE_OPENAI_DEPLOYMENT", "").strip()
        or os.environ.get("GPT4_LLM_MODEL_DEPLOYMENT_NAME", "").strip()
    )


def apply_autogen_azure_compat() -> None:
    """Patch ag2 OpenAIClient to honor env deployment names and quiet cost warnings."""
    global _applied
    if _applied:
        return

    from autogen.oai.client import OpenAIClient
    from autogen.oai.openai_utils import OAI_PRICE1K

    _orig_create = OpenAIClient.create
    _orig_cost = OpenAIClient.cost

    def create(self: Any, params: dict[str, Any]) -> Any:  # noqa: ANN401
        dep = _configured_deployment()
        model = params.get("model")
        # Restore env deployment when ag2 stripped dots (gpt-5.4 -> gpt-54).
        if dep and isinstance(model, str) and model == dep.replace(".", ""):
            params = {**params, "model": dep}
        return _orig_create(self, params)

    def cost(self: Any, response: Any) -> float:  # noqa: ANN401
        model = getattr(response, "model", None)
        if model not in OAI_PRICE1K:
            dep = _configured_deployment()
            # Azure returns underlying snapshot ids (deployment + date suffix).
            if dep and isinstance(model, str) and (model == dep or model.startswith(f"{dep}-")):
                return 0.0
            logger.warning(
                'Model %s is not found. The cost will be 0. In your config_list, add field '
                '{"price" : [prompt_price_per_1k, completion_token_price_per_1k]} for customized pricing.',
                model,
            )
            return 0.0
        return _orig_cost(self, response)

    OpenAIClient.create = create  # type: ignore[method-assign]
    OpenAIClient.cost = cost  # type: ignore[method-assign]
    _applied = True


__all__ = ["apply_autogen_azure_compat"]

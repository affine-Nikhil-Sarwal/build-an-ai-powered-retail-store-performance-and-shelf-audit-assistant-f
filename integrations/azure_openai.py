"""Azure OpenAI chat and vision client with token-budget detect-and-retry."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import ConfigurationError, Settings
from config.azure_openai_token_param import invoke_with_output_token_budget
from config.llm_json import extract_json_dict
from integrations.base import unwrap_retry_error


class AzureOpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: AzureOpenAI | None = None
        if settings.dry_run:
            return
        if not settings.azure_openai_api_key:
            return
        if not settings.azure_openai_endpoint:
            return
        if not settings.effective_deployment():
            return
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )

    def _require_client(self) -> AzureOpenAI:
        if self.settings.dry_run or self._client is None:
            if not self.settings.azure_openai_api_key:
                raise ConfigurationError("Set AZURE_OPENAI_API_KEY")
            if not self.settings.azure_openai_endpoint:
                raise ConfigurationError("Set AZURE_OPENAI_ENDPOINT")
            if not self.settings.effective_deployment():
                raise ConfigurationError("Set AZURE_OPENAI_DEPLOYMENT")
            raise ConfigurationError("Azure OpenAI client is not configured")
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        deployment: str | None = None,
        max_tokens: int = 1200,
        response_format: dict[str, str] | None = None,
    ) -> str:
        if self.settings.dry_run:
            raise RuntimeError("chat_completion unavailable in dry_run mode")
        client = self._require_client()
        dep = deployment or self.settings.effective_deployment()
        kwargs: dict[str, Any] = {"model": dep, "messages": messages}
        if response_format:
            kwargs["response_format"] = response_format

        def _create(**extra: Any) -> Any:
            return client.chat.completions.create(**{**kwargs, **extra})

        response = invoke_with_output_token_budget(
            _create,
            deployment=dep,
            token_budget=max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        deployment: str | None = None,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        content = self.chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            deployment=deployment,
            max_tokens=max_tokens,
        )
        return extract_json_dict(content)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def vision_json(
        self,
        *,
        system: str,
        user_text: str,
        image_paths: list[str],
        deployment: str | None = None,
        max_tokens: int = 1200,
    ) -> dict[str, Any]:
        if self.settings.dry_run:
            raise RuntimeError("vision_json unavailable in dry_run mode")
        client = self._require_client()
        dep = deployment or self.settings.effective_vision_deployment()
        content_parts: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for image_path in image_paths:
            path = Path(image_path)
            mime, _ = mimetypes.guess_type(path.name)
            mime = mime or "image/jpeg"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                }
            )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": content_parts},
        ]

        def _create(**extra: Any) -> Any:
            return client.chat.completions.create(
                model=dep,
                messages=messages,
                **extra,
            )

        response = invoke_with_output_token_budget(
            _create,
            deployment=dep,
            token_budget=max_tokens,
        )
        content = response.choices[0].message.content or ""
        return extract_json_dict(content)

    async def health_check(self) -> dict[str, str]:
        if self.settings.dry_run:
            return {"azure_openai": "skipped", "reason": "dry_run"}
        if self._client is None:
            missing = []
            if not self.settings.azure_openai_api_key:
                missing.append("AZURE_OPENAI_API_KEY")
            if not self.settings.azure_openai_endpoint:
                missing.append("AZURE_OPENAI_ENDPOINT")
            if not self.settings.effective_deployment():
                missing.append("AZURE_OPENAI_DEPLOYMENT")
            return {
                "azure_openai": "error",
                "reason": "Missing: " + ", ".join(missing) if missing else "client not initialized",
            }
        dep = self.settings.effective_deployment()
        try:
            client = self._require_client()

            def _create(**extra: Any) -> Any:
                return client.chat.completions.create(
                    model=dep,
                    messages=[{"role": "user", "content": "Reply with OK"}],
                    **extra,
                )

            invoke_with_output_token_budget(_create, deployment=dep, token_budget=5)
            return {"azure_openai": "ok", "deployment": dep}
        except Exception as exc:
            return {"azure_openai": "error", "reason": unwrap_retry_error(exc)}

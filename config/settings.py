"""Pydantic settings loaded from repo-root .env via absolute path."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_openai_api_key: str = Field(..., validation_alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(..., validation_alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = Field(..., validation_alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(
        default="2024-02-15-preview",
        validation_alias="AZURE_OPENAI_API_VERSION",
    )
    azure_openai_vision_deployment: str | None = Field(
        default=None,
        validation_alias="AZURE_OPENAI_VISION_DEPLOYMENT",
    )
    azure_openai_token_param: str | None = Field(
        default=None,
        validation_alias="AZURE_OPENAI_TOKEN_PARAM",
    )
    gpt4_llm_model_deployment_name: str | None = Field(
        default=None,
        validation_alias="GPT4_LLM_MODEL_DEPLOYMENT_NAME",
    )
    upload_root: str = Field(default="data/uploads", validation_alias="UPLOAD_ROOT")
    roboflow_api_key: str | None = Field(default=None, validation_alias="ROBOFLOW_API_KEY")
    azure_storage_connection_string: str | None = Field(
        default=None,
        validation_alias="AZURE_STORAGE_CONNECTION_STRING",
    )
    dry_run: bool = Field(default=False, validation_alias="DRY_RUN")

    def effective_deployment(self) -> str:
        return (
            self.azure_openai_deployment.strip()
            or (self.gpt4_llm_model_deployment_name or "").strip()
        )

    def effective_vision_deployment(self) -> str:
        return (self.azure_openai_vision_deployment or self.effective_deployment()).strip()

    def upload_path(self) -> Path:
        return Path(self.upload_root).resolve()

    def export_to_environ(self) -> None:
        import os

        os.environ.setdefault("AZURE_OPENAI_API_KEY", self.azure_openai_api_key)
        os.environ.setdefault("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint)
        dep = self.effective_deployment()
        if dep:
            os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", dep)
            os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", dep)


@lru_cache(maxsize=2)
def get_settings(*, dry_run: bool = False) -> Settings:
    if dry_run:
        root = Path(__file__).resolve().parent.parent / "data" / "uploads"
        root.mkdir(parents=True, exist_ok=True)
        return Settings.model_construct(
            azure_openai_api_key="",
            azure_openai_endpoint="",
            azure_openai_deployment="",
            azure_openai_api_version="2024-02-15-preview",
            upload_root=str(root),
            dry_run=True,
        )
    try:
        settings = Settings()
    except Exception as exc:
        raise ConfigurationError(
            "Missing required environment configuration. "
            "Copy .env.example to .env and set AZURE_OPENAI_API_KEY, "
            "AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT."
        ) from exc
    return settings

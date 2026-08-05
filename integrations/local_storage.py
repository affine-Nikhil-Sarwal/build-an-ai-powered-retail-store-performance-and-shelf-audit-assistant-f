"""Local filesystem storage for uploaded documents and images."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from config.settings import ConfigurationError, Settings
from integrations.base import unwrap_retry_error


class LocalStorageClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.upload_path()

    def ensure_writable(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise ConfigurationError(
                f"Upload root is not writable: {self.root}"
            ) from exc

    def create_job_dir(self, job_id: str | None = None) -> tuple[str, Path]:
        self.ensure_writable()
        jid = job_id or str(uuid.uuid4())
        job_dir = self.root / jid
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "documents").mkdir(exist_ok=True)
        (job_dir / "images").mkdir(exist_ok=True)
        (job_dir / "crops").mkdir(exist_ok=True)
        return jid, job_dir

    def persist_file(self, source_path: str | Path, dest_dir: Path, filename: str) -> str:
        src = Path(source_path)
        dest = dest_dir / filename
        shutil.copy2(src, dest)
        return str(dest.resolve())

    async def health_check(self) -> dict[str, str]:
        try:
            self.ensure_writable()
            return {"local_storage": "ok", "path": str(self.root)}
        except Exception as exc:
            return {"local_storage": "error", "reason": unwrap_retry_error(exc)}

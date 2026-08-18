"""Generate a downloadable PDF summary report from audit workflow output."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz

from config.settings import Settings


def _resolve_job_id(result: dict[str, Any]) -> str | None:
    package = result.get("validated_upload_package") or {}
    job_id = package.get("job_id")
    if job_id:
        return str(job_id)
    return None


def _report_output_path(settings: Settings, job_id: str) -> Path:
    return settings.upload_path() / job_id / "reports" / "audit_summary.pdf"


def _wrap_text(text: str, *, max_chars: int = 92) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        extra = len(word) if not current else len(word) + 1
        if current and length + extra > max_chars:
            lines.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += extra
    if current:
        lines.append(" ".join(current))
    return lines


class _PdfWriter:
    def __init__(self) -> None:
        self._doc = fitz.open()
        self._page = self._doc.new_page(width=595, height=842)
        self._margin = 54
        self._bottom = 790
        self._y = 54
        self._page_width = 595

    def _ensure_space(self, needed: float) -> None:
        if self._y + needed <= self._bottom:
            return
        self._page = self._doc.new_page(width=595, height=842)
        self._y = 54

    def heading(self, text: str, *, size: float = 14) -> None:
        self._ensure_space(size + 10)
        self._page.insert_text(
            (self._margin, self._y),
            text,
            fontsize=size,
            fontname="helv",
        )
        self._y += size + 8

    def subheading(self, text: str, *, size: float = 11) -> None:
        self._ensure_space(size + 8)
        self._page.insert_text(
            (self._margin, self._y),
            text,
            fontsize=size,
            fontname="helv",
        )
        self._y += size + 6

    def paragraph(self, text: str, *, size: float = 10, indent: float = 0) -> None:
        for line in _wrap_text(text):
            self._ensure_space(size + 4)
            self._page.insert_text(
                (self._margin + indent, self._y),
                line,
                fontsize=size,
                fontname="helv",
            )
            self._y += size + 4

    def bullet(self, text: str, *, size: float = 10) -> None:
        self._ensure_space(size + 4)
        self._page.insert_text(
            (self._margin, self._y),
            f"• {text}",
            fontsize=size,
            fontname="helv",
        )
        self._y += size + 4

    def spacer(self, height: float = 8) -> None:
        self._y += height

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._doc.save(path)
        self._doc.close()
        return path.resolve()


def build_audit_summary_pdf(result: dict[str, Any], output_path: Path) -> Path:
    """Render prioritized issues, confidence scores, and actions into a PDF report."""
    writer = _PdfWriter()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    package = result.get("validated_upload_package") or {}
    job_id = package.get("job_id") or "unknown"
    narrative = str(result.get("one_page_narrative_executive_brief") or "").strip()
    prioritized = list(result.get("prioritized_issue_list") or [])
    recommendations = list(result.get("free_form_corrective_action_recommendations") or [])
    confidence = result.get("confidence_notes_and_insufficient_evidence_flags") or {}

    writer.heading("Retail Shelf Audit Summary Report", size=16)
    writer.paragraph(f"Job ID: {job_id}")
    writer.paragraph(f"Generated: {generated_at}")
    writer.spacer()

    writer.subheading("Executive Summary")
    writer.paragraph(narrative or "No executive summary was produced for this audit.")
    writer.spacer()

    writer.subheading("Prioritized Issues")
    if not prioritized:
        writer.paragraph("No prioritized issues met the evidence threshold.")
    else:
        for issue in prioritized:
            rank = issue.get("rank", "?")
            category = issue.get("category") or "General"
            description = issue.get("description") or "No description"
            confidence_score = issue.get("confidence")
            priority_band = issue.get("priority_band") or issue.get("severity") or "n/a"
            score_text = f"{float(confidence_score):.2f}" if confidence_score is not None else "n/a"
            writer.bullet(
                f"#{rank} [{priority_band}] {category}: {description} "
                f"(confidence: {score_text})"
            )
            rationale = issue.get("rationale")
            if rationale:
                writer.paragraph(f"Rationale: {rationale}", indent=12)
    writer.spacer()

    writer.subheading("Recommended Corrective Actions")
    if not recommendations:
        writer.paragraph("No corrective actions were generated.")
    else:
        for rec in recommendations:
            if isinstance(rec, dict):
                text = rec.get("recommendation") or rec.get("action_text") or str(rec)
                issue_id = rec.get("issue_id")
                if issue_id:
                    writer.bullet(f"[{issue_id}] {text}")
                else:
                    writer.bullet(str(text))
            else:
                writer.bullet(str(rec))
    writer.spacer()

    writer.subheading("Confidence Notes")
    overall = confidence.get("overall_confidence")
    if overall is not None:
        writer.paragraph(f"Overall confidence: {float(overall):.2f}")
    flags = list(confidence.get("per_issue_flags") or [])
    if flags:
        writer.paragraph("Per-issue evidence flags:")
        for flag in flags:
            issue_id = flag.get("issue_id") or "unknown"
            insufficient = flag.get("insufficient_evidence")
            conflict = flag.get("conflict_detected")
            writer.bullet(
                f"{issue_id}: insufficient_evidence={insufficient}, "
                f"conflict_detected={conflict}"
            )
    rejected = list(confidence.get("rejected_image_paths") or [])
    if rejected:
        writer.paragraph(f"Rejected shelf images: {len(rejected)}")
    ocr_note = confidence.get("ocr_quality_notes")
    if ocr_note:
        writer.paragraph(f"OCR quality: {ocr_note}")

    return writer.save(output_path)


def generate_audit_summary_pdf(result: dict[str, Any], *, settings: Settings) -> Path:
    """Generate and persist the audit summary PDF for a completed workflow result."""
    job_id = _resolve_job_id(result)
    if not job_id:
        raise ValueError("Cannot generate PDF without validated_upload_package.job_id")
    output_path = _report_output_path(settings, job_id)
    return build_audit_summary_pdf(result, output_path)

"""Handler for weekly draft generation."""

from __future__ import annotations

from research_automation.config import load_settings
from research_automation.logging_config import configure_logging
from research_automation.pipeline.draft import DraftRequest, generate_draft


def handler(event: dict | None = None, context: object | None = None) -> dict:
    """AWS Lambda compatible entry point for weekly draft generation."""

    settings = load_settings()
    configure_logging(settings.log_level)
    draft = generate_draft(DraftRequest(title="Weekly Research Draft", articles=[]))
    return {"ok": True, "draft": draft.content}


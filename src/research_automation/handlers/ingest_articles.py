"""Handler for article ingestion."""

from __future__ import annotations

from research_automation.config import load_settings
from research_automation.logging_config import configure_logging
from research_automation.pipeline.collect import collect_articles


def handler(event: dict | None = None, context: object | None = None) -> dict:
    """AWS Lambda compatible entry point for article ingestion."""

    settings = load_settings()
    configure_logging(settings.log_level)
    articles = collect_articles([])
    return {"ok": True, "article_count": len(articles)}


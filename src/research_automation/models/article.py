"""Article domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from research_automation.utils.dates import utc_now


@dataclass
class Article:
    """Normalized article record used throughout the pipeline."""

    title: str
    url: str
    canonical_url: str
    source_name: str
    source_page_id: str
    published_date: datetime | None = None
    collected_date: datetime = field(default_factory=utc_now)
    snippet: str = ""
    region: list[str] = field(default_factory=list)
    topic_focus: list[str] = field(default_factory=list)
    url_hash: str = ""
    content_hash: str = ""
    image_url: str = ""


@dataclass
class EnrichedArticle:
    """OpenAI-generated enrichment payload."""

    summary: str
    why_it_matters: str
    relevance_score: int
    topic: list[str] = field(default_factory=list)
    region: list[str] = field(default_factory=list)
    newsletter_angle: str = ""
    sns_hook: str = ""

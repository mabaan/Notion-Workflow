"""Source domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Source:
    """Configuration for a source of research articles."""

    name: str
    feed_url: str = ""
    source_url: str = ""
    source_type: str = "Publisher"
    collection_method: str = ""
    region: list[str] = field(default_factory=list)
    topic_focus: list[str] = field(default_factory=list)
    editorial_quality: float | None = None
    credibility: str = ""
    acquisition_priority: str = ""
    check_frequency: str = ""
    last_attempt: datetime | None = None
    last_success: datetime | None = None
    notion_page_id: str = ""


@dataclass(frozen=True)
class SourceAttempt:
    """Outcome of contacting one publisher feed or discovery provider."""

    source_page_id: str
    source_name: str
    attempted_at: datetime
    outcome: str
    article_count: int = 0
    error: str = ""
    duration_ms: int = 0

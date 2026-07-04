"""Source domain model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Source:
    """Configuration for a source of research articles."""

    name: str
    feed_url: str
    source_url: str = ""
    collection_method: str = ""
    region: list[str] = field(default_factory=list)
    topic_focus: list[str] = field(default_factory=list)
    credibility: str = ""
    priority: str = ""
    check_frequency: str = ""
    notion_page_id: str = ""

"""Article domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """Normalized article record used throughout the pipeline."""

    url: str
    title: str = ""
    source: str = ""
    author: str = ""
    published_at: datetime | None = None
    summary: str = ""
    tags: list[str] = field(default_factory=list)


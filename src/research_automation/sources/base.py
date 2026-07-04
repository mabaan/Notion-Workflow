"""Base source adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from research_automation.models.article import Article
from research_automation.models.source import Source


class ArticleSource(ABC):
    """Common interface for article sources."""

    def __init__(self, source: Source) -> None:
        self.source = source

    @abstractmethod
    def collect(self) -> list[Article]:
        """Return articles from the source."""

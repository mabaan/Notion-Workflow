"""Base source adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from research_automation.models.article import Article


class ArticleSource(ABC):
    """Common interface for article sources."""

    @abstractmethod
    def collect(self) -> Iterable[Article]:
        """Return articles from the source."""


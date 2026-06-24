"""API source adapter placeholder."""

from __future__ import annotations

from collections.abc import Iterable

from research_automation.models.article import Article
from research_automation.sources.base import ArticleSource


class ApiSource(ArticleSource):
    """Collect articles from an HTTP API."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def collect(self) -> Iterable[Article]:
        """Return articles discovered from the configured API."""

        return []


"""Manual link source adapter."""

from __future__ import annotations

from collections.abc import Iterable

from research_automation.models.article import Article
from research_automation.sources.base import ArticleSource


class ManualLinksSource(ArticleSource):
    """Collect articles from a manually supplied list of URLs."""

    def __init__(self, urls: list[str]) -> None:
        self.urls = urls

    def collect(self) -> Iterable[Article]:
        """Return one article shell per manual URL."""

        return [Article(url=url) for url in self.urls]


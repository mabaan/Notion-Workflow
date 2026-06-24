"""RSS source adapter placeholder."""

from __future__ import annotations

from collections.abc import Iterable

from research_automation.models.article import Article
from research_automation.sources.base import ArticleSource


class RssSource(ArticleSource):
    """Collect articles from RSS feed URLs."""

    def __init__(self, feed_urls: list[str]) -> None:
        self.feed_urls = feed_urls

    def collect(self) -> Iterable[Article]:
        """Return articles discovered from RSS feeds."""

        return []


"""Article collection pipeline step."""

from __future__ import annotations

from collections.abc import Iterable

from research_automation.models.article import Article
from research_automation.sources.base import ArticleSource


def collect_articles(sources: Iterable[ArticleSource]) -> list[Article]:
    """Collect articles from all configured sources."""

    articles: list[Article] = []
    for source in sources:
        articles.extend(source.collect())
    return articles


"""Article deduplication helpers."""

from __future__ import annotations

from collections.abc import Iterable

from research_automation.models.article import Article
from research_automation.utils.hashing import stable_hash


def article_dedupe_key(article: Article) -> str:
    """Build a stable key for article deduplication."""

    if article.url:
        return stable_hash(article.url.strip().lower())
    return stable_hash(f"{article.title}|{article.published_at}")


def deduplicate_articles(articles: Iterable[Article]) -> list[Article]:
    """Return articles with duplicate URLs or title/date keys removed."""

    seen: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        key = article_dedupe_key(article)
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


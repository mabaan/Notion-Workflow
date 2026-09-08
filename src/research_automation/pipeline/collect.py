"""Concurrent publisher collection with structured per-source outcomes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import logging
from time import perf_counter

from research_automation.models.article import Article
from research_automation.models.source import Source, SourceAttempt
from research_automation.sources.rss import (
    FeedHttpError,
    FeedParseError,
    FeedUnchanged,
    RssSource,
)
from research_automation.utils.dates import utc_now

logger = logging.getLogger(__name__)
SUPPORTED_COLLECTION_METHODS = {"RSS", "Google News RSS", "Website"}


@dataclass
class CollectionResult:
    """Collected articles, actual attempts, and intentionally skipped sources."""

    articles: list[Article] = field(default_factory=list)
    attempts: list[SourceAttempt] = field(default_factory=list)
    skipped_sources: list[str] = field(default_factory=list)

    @property
    def source_errors(self) -> list[str]:
        """Compatibility view of failed attempts."""

        return [
            f"{attempt.source_name}: {attempt.error}"
            for attempt in self.attempts
            if attempt.error
        ]


def collect_articles(
    sources: list[Source],
    *,
    max_workers: int = 6,
) -> CollectionResult:
    """Contact supported due publishers concurrently, then sort deterministically."""

    result = CollectionResult()
    supported: list[Source] = []
    for source in sources:
        if source.collection_method not in SUPPORTED_COLLECTION_METHODS:
            message = (
                f"Skipped {source.name}: unsupported direct collection method "
                f"{source.collection_method or 'Unknown'}"
            )
            logger.info(message)
            result.skipped_sources.append(message)
            continue
        supported.append(source)

    if supported:
        worker_count = max(1, min(max_workers, 6, len(supported)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_sources = {
                executor.submit(_collect_one, source): source for source in supported
            }
            for future in as_completed(future_sources):
                articles, attempt = future.result()
                result.articles.extend(articles)
                result.attempts.append(attempt)

    result.articles.sort(
        key=lambda article: (
            article.publisher_key,
            article.published_date.isoformat() if article.published_date else "",
            article.canonical_url,
            article.title.casefold(),
        )
    )
    result.attempts.sort(key=lambda attempt: (attempt.source_name.casefold(), attempt.source_page_id))
    result.skipped_sources.sort(key=str.casefold)
    return result


def _collect_one(source: Source) -> tuple[list[Article], SourceAttempt]:
    attempted_at = utc_now()
    started = perf_counter()
    articles: list[Article] = []
    outcome = "Success"
    error = ""
    try:
        articles = RssSource(source).collect()
        if not articles:
            outcome = "Empty"
    except FeedUnchanged:
        outcome = "Unchanged"
    except FeedParseError as exc:
        outcome = "Parse Error"
        error = str(exc)
        logger.warning("Parse failure for %s: %s", source.name, exc)
    except FeedHttpError as exc:
        outcome = "HTTP Error"
        error = str(exc)
        logger.warning("HTTP failure for %s: %s", source.name, exc)
    except Exception as exc:  # defensive classification around third-party parsers
        outcome = "Parse Error"
        error = str(exc)
        logger.exception("Unexpected collection failure for %s", source.name)

    duration_ms = max(0, round((perf_counter() - started) * 1000))
    return articles, SourceAttempt(
        source_page_id=source.notion_page_id,
        source_name=source.name,
        attempted_at=attempted_at,
        outcome=outcome,
        article_count=len(articles),
        error=error,
        duration_ms=duration_ms,
    )

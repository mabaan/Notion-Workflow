"""Article collection pipeline step."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from research_automation.models.article import Article
from research_automation.models.source import Source
from research_automation.sources.rss import RssSource

logger = logging.getLogger(__name__)


@dataclass
class CollectionResult:
    """Collected articles plus non-fatal source issues."""

    articles: list[Article] = field(default_factory=list)
    source_errors: list[str] = field(default_factory=list)
    skipped_sources: list[str] = field(default_factory=list)


def collect_articles(sources: list[Source]) -> CollectionResult:
    """Collect articles from supported source types."""

    result = CollectionResult()
    for source in sources:
        if source.collection_method not in {"RSS", "Google News RSS", "Website"}:
            message = (
                f"Skipping source {source.name} with unsupported collection method "
                f"{source.collection_method or 'Unknown'}."
            )
            logger.info(message)
            result.skipped_sources.append(message)
            continue

        try:
            collector = RssSource(source)
            result.articles.extend(collector.collect())
        except Exception as exc:
            message = f"{source.name}: {exc}"
            logger.exception("Failed collecting from %s", source.name)
            result.source_errors.append(message)

    return result

"""Objective input preparation for metadata classification.

There is no editorial keyword/geography screen, retrieval, local-state write
or Notion operation here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from research_automation.models.article import Article
from research_automation.models.classification import ClassificationInput
from research_automation.utils.hashing import build_content_hash, build_url_hash
from research_automation.utils.urls import clean_url, url_hostname


@dataclass(frozen=True)
class PrecheckExclusion:
    article_id: str
    url: str
    reason: str
    input_index: int = 0


@dataclass
class PreparedClassifications:
    inputs: list[ClassificationInput] = field(default_factory=list)
    excluded: list[PrecheckExclusion] = field(default_factory=list)


def prepare_classification_inputs(
    articles: Iterable[Article], *, now: datetime, freshness_days: int = 7,
    excluded_urls: Iterable[str] = (), seen_url_hashes: Iterable[str] = (),
) -> PreparedClassifications:
    """Keep objective prechecks only; expose every exclusion and retain metadata.

    Callers supply processed/Notion URLs or hashes; this function loads no state.
    Stable IDs are hashes of canonical URLs. Duplicate copies remain visible in
    excluded, but only one representative per URL is sent for classification.
    """

    if freshness_days <= 0:
        raise ValueError("freshness_days must be positive")
    prepared = PreparedClassifications()
    seen = set(seen_url_hashes)
    urls = {clean_url(url) for url in excluded_urls if url}
    cutoff = now.replace(tzinfo=UTC) if now.tzinfo is None else now
    cutoff -= timedelta(days=freshness_days)
    for index, article in enumerate(articles):
        article_id = build_content_hash(article.title, article.source_name)
        reason = ""
        try:
            canonical = clean_url(article.canonical_url or article.url)
            original = clean_url(article.url or canonical)
            parts = urlsplit(canonical)
            if parts.scheme not in {"http", "https"} or not parts.hostname or any(c.isspace() for c in parts.hostname):
                raise ValueError("invalid URL")
            article_id = build_url_hash(canonical)
        except ValueError:
            canonical = original = ""
            reason = "invalid URL"
        words = [word for word in article.title.split() if any(char.isalnum() for char in word)]
        if not reason and (len(article.title.strip()) < 12 or len(words) < 3):
            reason = "invalid title"
        if not reason and not isinstance(article.published_date, datetime):
            reason = "unknown or invalid publication date"
        if not reason:
            published = article.published_date
            published = published.replace(tzinfo=UTC) if published.tzinfo is None else published
            if published < cutoff:
                reason = "outside freshness window"
        if not reason and any(
            host == "somamater.com" or host.endswith(".somamater.com")
            for host in (url_hostname(original), url_hostname(canonical))
        ):
            reason = "self-published content"
        if not reason and (canonical in urls or original in urls or article_id in seen or build_url_hash(original) in seen):
            reason = "duplicate or previously processed URL"
        if reason:
            prepared.excluded.append(PrecheckExclusion(article_id, article.url, reason, index))
            continue
        urls.update((canonical, original))
        seen.add(article_id)
        prepared.inputs.append(ClassificationInput(
            article_id, article.title, article.snippet, article.source_name,
            article.published_date, tuple(article.region),
        ))
    return prepared

"""RSS source adapter."""

from __future__ import annotations

from datetime import UTC, datetime
import time

import feedparser

from research_automation.models.article import Article
from research_automation.pipeline.clean import clean_snippet, clean_text
from research_automation.sources.base import ArticleSource
from research_automation.utils.dates import utc_now
from research_automation.utils.urls import extract_entry_url


class RssSource(ArticleSource):
    """Collect articles from RSS feed URLs."""

    def collect(self) -> list[Article]:
        """Return articles discovered from RSS feeds."""

        feed = feedparser.parse(self.source.feed_url)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Could not parse feed: {self.source.feed_url}")

        articles: list[Article] = []
        collected_at = utc_now()

        for entry in feed.entries:
            url = extract_entry_url(entry)
            if not url:
                continue

            title = clean_text(str(entry.get("title") or "")) or url
            summary = clean_snippet(
                str(entry.get("summary") or entry.get("description") or "")
            )

            articles.append(
                Article(
                    title=title,
                    url=url,
                    canonical_url=url,
                    source_name=self.source.name,
                    source_page_id=self.source.notion_page_id,
                    published_date=_entry_datetime(entry),
                    collected_date=collected_at,
                    snippet=summary,
                    region=list(self.source.region),
                    topic_focus=list(self.source.topic_focus),
                    image_url=_entry_image_url(entry),
                )
            )

        return articles


def _entry_datetime(entry: dict) -> datetime | None:
    """Convert feedparser timestamps to timezone-aware datetimes."""

    for field_name in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(field_name)
        if isinstance(value, time.struct_time):
            return datetime(*value[:6], tzinfo=UTC)
    return None


def _entry_image_url(entry: dict) -> str:
    """Return the best feed-level image URL for an entry."""

    for field_name in ("media_content", "media_thumbnail"):
        items = entry.get(field_name) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate = str(item.get("url") or "").strip()
            if candidate:
                return candidate

    for field_name in ("image", "itunes_image"):
        payload = entry.get(field_name) or {}
        if isinstance(payload, dict):
            candidate = str(payload.get("href") or payload.get("url") or "").strip()
            if candidate:
                return candidate

    return ""

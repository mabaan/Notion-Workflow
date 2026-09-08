"""RSS source adapter."""

from __future__ import annotations

from datetime import UTC, datetime
import time

import feedparser
import httpx

from research_automation.models.article import Article
from research_automation.pipeline.clean import clean_snippet, clean_text
from research_automation.sources.base import ArticleSource
from research_automation.utils.dates import utc_now
from research_automation.utils.urls import extract_entry_url, url_hostname


class RssSource(ArticleSource):
    """Collect articles from RSS feed URLs."""

    def collect(self) -> list[Article]:
        """Return articles discovered from RSS feeds."""

        feed_bytes = fetch_feed_bytes(self.source.feed_url)
        feed = feedparser.parse(feed_bytes)
        if feed.bozo and not feed.entries:
            detail = str(getattr(feed, "bozo_exception", "invalid feed"))
            raise FeedParseError(f"Could not parse feed: {detail}")

        articles: list[Article] = []
        collected_at = utc_now()

        for entry in feed.entries:
            url = extract_entry_url(entry)
            if not url:
                continue

            title = clean_text(str(entry.get("title") or ""))
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
                    source_editorial_quality=self.source.editorial_quality,
                    publisher_key=self.source.notion_page_id or url_hostname(url),
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


class FeedHttpError(RuntimeError):
    """A publisher feed could not be fetched successfully."""


class FeedParseError(RuntimeError):
    """Fetched bytes were not a usable feed."""


class FeedUnchanged(RuntimeError):
    """The server explicitly reported that the feed is unchanged."""


def fetch_feed_bytes(url: str, *, max_retries: int = 2) -> bytes:
    """Fetch feed bytes with bounded retries and explicit phase timeouts."""

    timeout = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
    transient_statuses = {408, 425, 429, 500, 502, 503, 504}
    last_error: Exception | None = None
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        for attempt_number in range(max_retries + 1):
            try:
                response = client.get(url)
                if response.status_code == 304:
                    raise FeedUnchanged("Feed returned HTTP 304 Not Modified")
                if response.status_code in transient_statuses and attempt_number < max_retries:
                    continue
                response.raise_for_status()
                return response.content
            except FeedUnchanged:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code in transient_statuses
                )
                if retryable and attempt_number < max_retries:
                    continue
                break
    raise FeedHttpError(f"Failed to fetch {url}: {last_error}") from last_error

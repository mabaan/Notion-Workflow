"""Quality-ordered discovery provider fallback for deficient regions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from time import perf_counter
from typing import Any

from research_automation.clients.brave_search_client import BraveSearchClient
from research_automation.clients.discovery_common import ProviderError, ProviderLimitError
from research_automation.clients.newsapi_client import NewsApiClient
from research_automation.config import Settings
from research_automation.models.article import Article
from research_automation.models.source import Source, SourceAttempt
from research_automation.utils.dates import utc_now
from research_automation.utils.hashing import build_content_hash, build_url_hash
from research_automation.utils.regions import (
    TARGET_REGION_ORDER,
    build_region_query,
    merge_region_labels,
)
from research_automation.utils.urls import clean_url, hostname_matches, url_hostname

logger = logging.getLogger(__name__)

REGION_SOURCE_PRIORITY = {
    "Global": ("Global",),
    "UAE": ("UAE", "GCC", "MENA", "Global"),
    "KSA": ("KSA", "GCC", "MENA", "Global"),
    "Egypt": ("Egypt", "MENA", "Global", "GCC"),
}
PROVIDER_NAME_MAP = {
    "brave": "brave",
    "brave search": "brave",
    "newsapi": "newsapi",
    "news api": "newsapi",
}
ACQUISITION_PRIORITY_RANK = {"Core": 0, "Secondary": 1, "Trial": 2}


@dataclass
class RequestBudget:
    brave_requests: int = 0
    newsapi_requests: int = 0


@dataclass
class DiscoveryService:
    """Invoke provider rows by provider quality without leaking it to publishers."""

    settings: Settings
    sources: list[Source]
    budget: RequestBudget = field(default_factory=RequestBudget)
    attempts: list[SourceAttempt] = field(default_factory=list)
    brave: BraveSearchClient | None = field(init=False)
    newsapi: NewsApiClient | None = field(init=False)

    def __post_init__(self) -> None:
        self.brave = (
            BraveSearchClient(self.settings.brave_search_api_key)
            if self.settings.brave_search_api_key
            else None
        )
        self.newsapi = (
            NewsApiClient(self.settings.news_api_key)
            if self.settings.news_api_key
            else None
        )

    @property
    def provider_order(self) -> tuple[str, ...]:
        """Order active provider rows by quality, then explicit acquisition priority."""

        rows: list[tuple[float, int, str, str]] = []
        for source in self.sources:
            if source.source_type != "Discovery Provider":
                continue
            provider_key = _provider_key_from_source_name(source.name)
            if provider_key is None:
                continue
            rows.append(
                (
                    -(source.editorial_quality or 0),
                    ACQUISITION_PRIORITY_RANK.get(source.acquisition_priority, 99),
                    provider_key,
                    source.notion_page_id,
                )
            )
        if not rows:
            return self.settings.news_discovery_providers
        ordered: list[str] = []
        for _, _, key, _ in sorted(rows):
            if key not in ordered:
                ordered.append(key)
        return tuple(ordered)

    def discover_articles(
        self,
        deficits: dict[str, int],
        *,
        max_per_region: int,
        excluded_hashes: set[str],
    ) -> list[Article]:
        """Return a bounded candidate pool only for regions that remain deficient."""

        articles: list[Article] = []
        seen = set(excluded_hashes)
        for region in TARGET_REGION_ORDER:
            if deficits.get(region, 0) <= 0:
                continue
            regional = self._discover_for_region(region, max_per_region, seen)
            for article in regional:
                if article.url_hash in seen:
                    continue
                seen.add(article.url_hash)
                articles.append(article)
        return sorted(
            articles,
            key=lambda article: (
                TARGET_REGION_ORDER.index(article.region[0]),
                -(article.source_editorial_quality or 0),
                article.canonical_url,
            ),
        )

    def _discover_for_region(
        self,
        region: str,
        limit: int,
        excluded_hashes: set[str],
    ) -> list[Article]:
        query = build_region_query(region, self.settings.discovery_topics)
        candidates: list[Article] = []
        candidate_hashes = set(excluded_hashes)
        for provider in self.provider_order:
            if len(candidates) >= limit:
                break
            provider_source = self._provider_source(provider)
            if provider_source is None:
                continue
            attempted_at = utc_now()
            started = perf_counter()
            request_count_before = self._request_count(provider)
            outcome = "Success"
            error = ""
            provider_results: list[Article] = []
            try:
                if provider == "brave":
                    if (
                        self.brave is None
                        or self.budget.brave_requests
                        >= self.settings.brave_max_requests_per_run
                    ):
                        continue
                    self.budget.brave_requests += 1
                    provider_results = self._brave_articles(region, query, provider_source)
                elif provider == "newsapi":
                    if (
                        self.newsapi is None
                        or self.budget.newsapi_requests
                        >= self.settings.newsapi_max_requests_per_run
                    ):
                        continue
                    self.budget.newsapi_requests += 1
                    provider_results = self._newsapi_articles(region, query, provider_source)
                else:
                    continue
                if not provider_results:
                    outcome = "Empty"
            except ProviderLimitError as exc:
                outcome = "HTTP Error"
                error = str(exc)
                logger.warning("%s failed for %s: %s", provider_source.name, region, exc)
            except ProviderError as exc:
                error = str(exc)
                outcome = "Parse Error" if "invalid json" in error.casefold() else "HTTP Error"
                logger.warning("%s failed for %s: %s", provider_source.name, region, exc)
            finally:
                # A health attempt exists only when an API request counter advanced.
                contacted = self._request_count(provider) > request_count_before
                if contacted:
                    self.attempts.append(
                        SourceAttempt(
                            source_page_id=provider_source.notion_page_id,
                            source_name=provider_source.name,
                            attempted_at=attempted_at,
                            outcome=outcome,
                            article_count=len(provider_results),
                            error=error,
                            duration_ms=max(0, round((perf_counter() - started) * 1000)),
                        )
                    )
            for article in provider_results:
                if article.url_hash in candidate_hashes:
                    continue
                candidate_hashes.add(article.url_hash)
                candidates.append(article)
                if len(candidates) >= limit:
                    break
        return candidates

    def _brave_articles(
        self,
        region: str,
        query: str,
        provider_source: Source,
    ) -> list[Article]:
        assert self.brave is not None
        language = self.settings.discovery_languages(region)[0]
        results = self.brave.search_news(query=query, count=10, search_lang=language)
        return self._map_results(region, results, provider_source, kind="brave")

    def _newsapi_articles(
        self,
        region: str,
        query: str,
        provider_source: Source,
    ) -> list[Article]:
        assert self.newsapi is not None
        language = self.settings.discovery_languages(region)[0]
        results = self.newsapi.search_everything(
            query=query,
            language=language,
            domains=self._preferred_source_domains(region),
            from_iso=(utc_now() - timedelta(days=self.settings.article_freshness_days)).date().isoformat(),
            to_iso=utc_now().date().isoformat(),
            page_size=10,
        )
        return self._map_results(region, results, provider_source, kind="newsapi")

    def _map_results(
        self,
        region: str,
        results: list[dict[str, Any]],
        provider_source: Source,
        *,
        kind: str,
    ) -> list[Article]:
        articles: list[Article] = []
        for result in results:
            url = clean_url(str(result.get("url") or ""))
            if not url:
                continue
            publisher = self._match_publisher(url)
            source_meta = result.get("source")
            result_source_name = (
                str(source_meta.get("name") or "").strip()
                if isinstance(source_meta, dict)
                else ""
            )
            title = str(result.get("title") or "").strip()
            snippet = str(
                result.get("description") or result.get("summary") or ""
            ).strip()
            hostname = url_hostname(url)
            articles.append(
                Article(
                    title=title,
                    url=url,
                    canonical_url=url,
                    source_name=(
                        publisher.name if publisher else result_source_name or hostname
                    ),
                    source_page_id=publisher.notion_page_id if publisher else "",
                    published_date=_parse_iso_datetime(
                        result.get("page_age")
                        if kind == "brave"
                        else result.get("publishedAt")
                    ),
                    collected_date=utc_now(),
                    snippet=snippet,
                    region=merge_region_labels(
                        [region],
                        publisher.region if publisher else [],
                    ),
                    topic_focus=list(publisher.topic_focus) if publisher else [],
                    source_editorial_quality=(
                        publisher.editorial_quality if publisher else None
                    ),
                    publisher_key=(
                        publisher.notion_page_id if publisher else hostname
                    ),
                    discovery_provider=provider_source.name,
                    url_hash=build_url_hash(url),
                    content_hash=build_content_hash(title, hostname),
                    image_url=(
                        clean_url(str(result.get("urlToImage") or ""))
                        if kind == "newsapi"
                        else ""
                    ),
                )
            )
        return sorted(
            articles,
            key=lambda article: (
                -(article.source_editorial_quality or 0),
                article.source_page_id == "",
                article.canonical_url,
            ),
        )

    def _preferred_source_domains(self, region: str) -> list[str]:
        labels = {
            label.casefold() for label in REGION_SOURCE_PRIORITY.get(region, ())
        }
        publishers = [
            source
            for source in self.sources
            if source.source_type == "Publisher"
            and any(label.casefold() in labels for label in source.region)
        ]
        publishers.sort(
            key=lambda source: (
                -(source.editorial_quality or 0),
                source.name.casefold(),
                source.notion_page_id,
            )
        )
        domains: list[str] = []
        for source in publishers:
            host = url_hostname(source.source_url or source.feed_url)
            if host and host not in domains:
                domains.append(host)
        return domains

    def _match_publisher(self, url: str) -> Source | None:
        host = url_hostname(url)
        matches = []
        for source in self.sources:
            if source.source_type != "Publisher":
                continue
            source_host = url_hostname(source.source_url or source.feed_url)
            if source_host and hostname_matches(host, source_host):
                matches.append(source)
        if not matches:
            return None
        return sorted(
            matches,
            key=lambda source: (
                -(source.editorial_quality or 0),
                source.name.casefold(),
                source.notion_page_id,
            ),
        )[0]

    def _provider_source(self, key: str) -> Source | None:
        matches = [
            source
            for source in self.sources
            if source.source_type == "Discovery Provider"
            and _provider_key_from_source_name(source.name) == key
        ]
        if not matches:
            return None
        return sorted(
            matches,
            key=lambda source: (
                -(source.editorial_quality or 0),
                ACQUISITION_PRIORITY_RANK.get(source.acquisition_priority, 99),
                source.notion_page_id,
            ),
        )[0]

    def _request_count(self, provider: str) -> int:
        if provider == "brave":
            return self.budget.brave_requests
        if provider == "newsapi":
            return self.budget.newsapi_requests
        return 0


def _provider_key_from_source_name(name: str) -> str | None:
    normalized = name.strip().casefold()
    for token, provider_key in PROVIDER_NAME_MAP.items():
        if token in normalized:
            return provider_key
    return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None

"""Regional quota planning and provider fallback discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from collections import deque
from typing import Any

from research_automation.clients.brave_search_client import BraveSearchClient
from research_automation.clients.discovery_common import (
    ProviderError,
    ProviderLimitError,
)
from research_automation.clients.newsapi_client import NewsApiClient
from research_automation.config import Settings
from research_automation.models.article import Article
from research_automation.models.source import Source
from research_automation.notion_schema import ARTICLE_QUEUE
from research_automation.utils.dates import current_workweek, utc_now
from research_automation.utils.hashing import build_content_hash, build_url_hash
from research_automation.utils.regions import (
    TARGET_REGION_ORDER,
    add_primary_region_count,
    build_region_query,
    infer_target_region_from_text,
    merge_region_labels,
    primary_target_region,
    target_deficits,
)
from research_automation.utils.urls import clean_url, hostname_matches, url_hostname

logger = logging.getLogger(__name__)

REGION_SOURCE_PRIORITY = {
    "Global": ("Global",),
    "UAE": ("UAE", "GCC", "MENA", "Global"),
    "KSA": ("KSA", "GCC", "MENA", "Global"),
    "Egypt": ("MENA", "Global", "GCC"),
}

PROVIDER_NAME_MAP = {
    "brave": "brave",
    "brave search": "brave",
    "newsapi": "newsapi",
    "news api": "newsapi",
}

PROVIDER_PRIORITY_RANK = {
    "Core": 0,
    "Secondary": 1,
    "Trial": 2,
}


@dataclass
class RequestBudget:
    """Per-run request counters for external providers."""

    brave_requests: int = 0
    newsapi_requests: int = 0


@dataclass
class DiscoveryService:
    """Discover top-up news articles when weekly buckets are underfilled."""

    settings: Settings
    sources: list[Source]
    budget: RequestBudget = field(default_factory=RequestBudget)
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

    def top_up_articles(
        self,
        deficits: dict[str, int],
        *,
        limit: int,
        excluded_hashes: set[str],
    ) -> list[Article]:
        """Return newly discovered articles to fill unmet regional quotas."""

        results: list[Article] = []
        seen_hashes = set(excluded_hashes)

        for region in TARGET_REGION_ORDER:
            while deficits.get(region, 0) > 0 and len(results) < limit:
                candidates = self._discover_for_region(region, deficits[region], seen_hashes)
                if not candidates:
                    break

                added = 0
                for article in candidates:
                    if article.url_hash in seen_hashes:
                        continue
                    results.append(article)
                    seen_hashes.add(article.url_hash)
                    deficits[region] -= 1
                    added += 1
                    if deficits[region] <= 0 or len(results) >= limit:
                        break

                if added == 0:
                    break

        return results

    @property
    def provider_order(self) -> tuple[str, ...]:
        """Return the active fallback provider order."""

        api_rows = []
        for source in self.sources:
            if source.collection_method != "API":
                continue

            provider_key = _provider_key_from_source_name(source.name)
            if provider_key is None:
                continue

            api_rows.append(
                (
                    PROVIDER_PRIORITY_RANK.get(source.priority, 99),
                    provider_key,
                )
            )

        if api_rows:
            ordered = []
            seen = set()
            for _, provider_key in sorted(api_rows):
                if provider_key in seen:
                    continue
                seen.add(provider_key)
                ordered.append(provider_key)
            return tuple(ordered)

        return self.settings.news_discovery_providers

    def _discover_for_region(
        self,
        region: str,
        deficit: int,
        excluded_hashes: set[str],
    ) -> list[Article]:
        query = build_region_query(region, self.settings.discovery_topics)
        candidates: list[Article] = []

        for provider in self.provider_order:
            provider_name = provider.casefold()

            try:
                if provider_name == "brave":
                    if self.brave is None or self.budget.brave_requests >= self.settings.brave_max_requests_per_run:
                        continue
                    self.budget.brave_requests += 1
                    provider_results = self._brave_articles(region, query)
                elif provider_name == "newsapi":
                    if self.newsapi is None or self.budget.newsapi_requests >= self.settings.newsapi_max_requests_per_run:
                        continue
                    self.budget.newsapi_requests += 1
                    provider_results = self._newsapi_articles(region, query)
                else:
                    logger.info("Skipping unknown discovery provider: %s", provider)
                    continue
            except ProviderLimitError as exc:
                logger.warning("%s quota unavailable for %s: %s", provider, region, exc)
                continue
            except ProviderError as exc:
                logger.warning("%s failed for %s: %s", provider, region, exc)
                continue

            for article in provider_results:
                if article.url_hash in excluded_hashes:
                    continue
                candidates.append(article)

            if len(candidates) >= deficit:
                break

        return candidates

    def _brave_articles(self, region: str, query: str) -> list[Article]:
        language = self.settings.discovery_languages(region)[0]
        results = self.brave.search_news(query=query, count=10, search_lang=language)
        return self._map_brave_results(region, results)

    def _newsapi_articles(self, region: str, query: str) -> list[Article]:
        week = current_workweek()
        language = self.settings.discovery_languages(region)[0]
        domains = self._preferred_source_domains(region)
        results = self.newsapi.search_everything(
            query=query,
            language=language,
            domains=domains,
            from_iso=week.start.isoformat(),
            to_iso=utc_now().date().isoformat(),
            page_size=10,
        )
        return self._map_newsapi_results(region, results)

    def _map_brave_results(
        self,
        region: str,
        results: list[dict[str, Any]],
    ) -> list[Article]:
        articles: list[Article] = []

        for result in results:
            url = clean_url(str(result.get("url") or ""))
            if not url:
                continue

            matched_source = self._match_source(url)
            article_region = merge_region_labels(
                [region],
                matched_source.region if matched_source else [],
            )
            title = str(result.get("title") or "").strip() or url
            snippet = str(result.get("description") or "").strip()

            articles.append(
                Article(
                    title=title,
                    url=url,
                    canonical_url=url,
                    source_name=matched_source.name if matched_source else url_hostname(url),
                    source_page_id=matched_source.notion_page_id if matched_source else "",
                    published_date=_parse_iso_datetime(result.get("page_age")),
                    collected_date=utc_now(),
                    snippet=snippet,
                    region=article_region,
                    topic_focus=list(matched_source.topic_focus) if matched_source else [],
                    url_hash=build_url_hash(url),
                    content_hash=build_content_hash(title, url_hostname(url)),
                )
            )

        return self._sort_articles_by_source_preference(region, articles)

    def _map_newsapi_results(
        self,
        region: str,
        results: list[dict[str, Any]],
    ) -> list[Article]:
        articles: list[Article] = []

        for result in results:
            url = clean_url(str(result.get("url") or ""))
            if not url:
                continue

            matched_source = self._match_source(url)
            source_name = ""
            source_meta = result.get("source")
            if isinstance(source_meta, dict):
                source_name = str(source_meta.get("name") or "").strip()

            title = str(result.get("title") or "").strip() or url
            description = str(result.get("description") or "").strip()
            article_region = merge_region_labels(
                [region],
                matched_source.region if matched_source else [],
            )

            articles.append(
                Article(
                    title=title,
                    url=url,
                    canonical_url=url,
                    source_name=matched_source.name if matched_source else source_name or url_hostname(url),
                    source_page_id=matched_source.notion_page_id if matched_source else "",
                    published_date=_parse_iso_datetime(result.get("publishedAt")),
                    collected_date=utc_now(),
                    snippet=description,
                    region=article_region,
                    topic_focus=list(matched_source.topic_focus) if matched_source else [],
                    url_hash=build_url_hash(url),
                    content_hash=build_content_hash(title, url_hostname(url)),
                    image_url=clean_url(str(result.get("urlToImage") or "")),
                )
            )

        return self._sort_articles_by_source_preference(region, articles)

    def _sort_articles_by_source_preference(
        self,
        region: str,
        articles: list[Article],
    ) -> list[Article]:
        preferred_hosts = self._preferred_source_domains(region)
        return sorted(
            articles,
            key=lambda article: (
                0 if any(hostname_matches(url_hostname(article.canonical_url), domain) for domain in preferred_hosts) else 1,
                article.source_page_id == "",
                article.title.casefold(),
            ),
        )

    def _preferred_source_domains(self, region: str) -> list[str]:
        preferred_labels = REGION_SOURCE_PRIORITY.get(region, ())
        domains: list[str] = []

        for source in self.sources:
            if not any(label in source.region for label in preferred_labels):
                continue
            host = url_hostname(source.source_url or source.feed_url)
            if host and host not in domains:
                domains.append(host)

        return domains

    def _match_source(self, url: str) -> Source | None:
        host = url_hostname(url)
        if not host:
            return None

        for source in self.sources:
            source_host = url_hostname(source.source_url or source.feed_url)
            if source_host and hostname_matches(host, source_host):
                return source
        return None


def count_weekly_region_coverage(
    notion,
    settings: Settings,
    dataset_meeting_page_id: str,
) -> dict[str, int]:
    """Count current-week Article Queue coverage by exact target region."""

    counts = {region: 0 for region in TARGET_REGION_ORDER}
    pages = notion.query_database(
        settings.notion_article_queue_database_id,
        filter_payload={
            "property": ARTICLE_QUEUE["dataset_meeting"],
            "relation": {"contains": dataset_meeting_page_id},
        },
    )

    for page in pages:
        properties = page.get("properties", {})
        labels = [
            option.get("name", "")
            for option in properties.get(ARTICLE_QUEUE["region"], {}).get("multi_select", [])
            if option.get("name")
        ]
        add_primary_region_count(counts, labels)

    return counts


def assign_article_target_region(article: Article) -> Article:
    """Augment an article with at most one exact quota region."""

    inferred = infer_target_region_from_text(f"{article.title}\n{article.snippet}")
    existing = primary_target_region(article.region)
    target = inferred or existing
    if not target:
        return article

    article.region = merge_region_labels([target], article.region)
    return article


def select_feed_articles_for_run(
    articles: list[Article],
    *,
    current_counts: dict[str, int],
    target_counts: dict[str, int],
    limit: int,
) -> tuple[list[Article], dict[str, int]]:
    """Reserve room for unmet quotas, then fill remaining slots with feed items."""

    planned_counts = dict(current_counts)
    selected: list[Article] = []
    selected_hashes: set[str] = set()
    region_buckets = {region: [] for region in TARGET_REGION_ORDER}
    remaining: list[Article] = []

    for article in articles:
        candidate = assign_article_target_region(article)
        region = primary_target_region(candidate.region)
        if region in region_buckets:
            region_buckets[region].append(candidate)
            continue
        remaining.append(candidate)

    for region in TARGET_REGION_ORDER:
        if len(selected) >= limit:
            break

        deficits = target_deficits(planned_counts, target_counts)
        if deficits.get(region, 0, ) <= 0:
            continue

        for candidate in _interleave_articles_by_source(region_buckets[region]):
            if candidate.url_hash and candidate.url_hash in selected_hashes:
                continue

            selected.append(candidate)
            if candidate.url_hash:
                selected_hashes.add(candidate.url_hash)
            add_primary_region_count(planned_counts, candidate.region)

            deficits = target_deficits(planned_counts, target_counts)
            if deficits.get(region, 0) <= 0 or len(selected) >= limit:
                break

    for region in TARGET_REGION_ORDER:
        remaining.extend(
            candidate
            for candidate in region_buckets[region]
            if not candidate.url_hash or candidate.url_hash not in selected_hashes
        )

    outstanding = sum(target_deficits(planned_counts, target_counts).values())
    generic_slots = max(0, limit - len(selected) - outstanding)
    selected.extend(_interleave_articles_by_source(remaining)[:generic_slots])

    return selected, target_deficits(planned_counts, target_counts)


def prioritize_articles_for_admission(
    articles: list[Article],
    *,
    current_counts: dict[str, int],
    target_counts: dict[str, int],
) -> list[Article]:
    """Order candidates so unmet target regions are exhausted before generic backfill."""

    deficits = target_deficits(current_counts, target_counts)
    region_buckets = {region: deque() for region in TARGET_REGION_ORDER}
    generic_articles: list[Article] = []

    for article in articles:
        region = primary_target_region(article.region)
        if region in region_buckets:
            region_buckets[region].append(article)
        else:
            generic_articles.append(article)

    prioritized: list[Article] = []
    deficit_regions = [
        region for region in TARGET_REGION_ORDER if deficits.get(region, 0) > 0
    ]

    prioritized.extend(_drain_round_robin(region_buckets, deficit_regions))
    remaining_regions = [
        region for region in TARGET_REGION_ORDER if region not in deficit_regions
    ]
    prioritized.extend(_drain_round_robin(region_buckets, remaining_regions))
    prioritized.extend(_interleave_articles_by_source(generic_articles))
    return prioritized


def choose_next_article_for_admission(
    articles: list[Article],
    *,
    current_counts: dict[str, int],
    target_counts: dict[str, int],
    source_counts: dict[str, int],
    max_per_source: int,
    deficits_only: bool,
    allow_source_cap_override: bool,
) -> Article | None:
    """Choose the next best candidate given live regional deficits and source caps."""

    deficits = target_deficits(current_counts, target_counts)
    region_buckets = {region: [] for region in TARGET_REGION_ORDER}
    generic_articles: list[Article] = []

    for article in articles:
        region = primary_target_region(article.region)
        if region in region_buckets:
            region_buckets[region].append(article)
        else:
            generic_articles.append(article)

    deficit_regions = sorted(
        (
            region
            for region in TARGET_REGION_ORDER
            if deficits.get(region, 0) > 0
        ),
        key=lambda region: (-deficits.get(region, 0), TARGET_REGION_ORDER.index(region)),
    )
    non_deficit_regions = [
        region for region in TARGET_REGION_ORDER if region not in deficit_regions
    ]

    search_regions = deficit_regions
    if not deficits_only:
        search_regions = [*deficit_regions, *non_deficit_regions]

    for region in search_regions:
        candidate = _pick_candidate_from_region(
            region_buckets[region],
            source_counts=source_counts,
            max_per_source=max_per_source,
            allow_source_cap_override=allow_source_cap_override,
        )
        if candidate is not None:
            return candidate

    if deficits_only:
        return None

    return _pick_candidate_from_region(
        generic_articles,
        source_counts=source_counts,
        max_per_source=max_per_source,
        allow_source_cap_override=allow_source_cap_override,
    )


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    candidate = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _provider_key_from_source_name(name: str) -> str | None:
    normalized = name.strip().casefold()
    for token, provider_key in PROVIDER_NAME_MAP.items():
        if token in normalized:
            return provider_key
    return None


def _interleave_articles_by_source(articles: list[Article]) -> list[Article]:
    """Spread generic backfill across sources instead of taking one source in sequence."""

    buckets: dict[str, deque[Article]] = {}
    source_order: list[str] = []

    for article in articles:
        source_key = article.source_name.strip() or "Unknown source"
        if source_key not in buckets:
            buckets[source_key] = deque()
            source_order.append(source_key)
        buckets[source_key].append(article)

    interleaved: list[Article] = []
    while source_order:
        next_round: list[str] = []
        for source_key in source_order:
            bucket = buckets[source_key]
            if bucket:
                interleaved.append(bucket.popleft())
            if bucket:
                next_round.append(source_key)
        source_order = next_round

    return interleaved


def _drain_round_robin(
    region_buckets: dict[str, deque[Article]],
    regions: list[str],
) -> list[Article]:
    ordered: list[Article] = []
    active_regions = [region for region in regions if region_buckets[region]]

    while active_regions:
        next_round: list[str] = []
        for region in active_regions:
            bucket = region_buckets[region]
            if bucket:
                ordered.append(bucket.popleft())
            if bucket:
                next_round.append(region)
        active_regions = next_round

    return ordered


def _pick_candidate_from_region(
    articles: list[Article],
    *,
    source_counts: dict[str, int],
    max_per_source: int,
    allow_source_cap_override: bool,
) -> Article | None:
    uncapped_candidate: Article | None = None
    capped_candidate: Article | None = None

    for article in articles:
        source_count = source_counts.get(article.source_name, 0)
        if source_count < max_per_source:
            uncapped_candidate = article
            break
        if capped_candidate is None:
            capped_candidate = article

    if uncapped_candidate is not None:
        return uncapped_candidate
    if allow_source_cap_override:
        return capped_candidate
    return None

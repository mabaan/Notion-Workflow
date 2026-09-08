"""Eligibility, bounded shortlisting, enrichment, and transitional ranking."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta

from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.candidate import CandidateEvaluation, CandidateResult
from research_automation.pipeline.relevance import (
    article_has_interest_geography,
    matched_company_topics,
)
from research_automation.utils.hashing import build_content_hash, build_url_hash
from research_automation.utils.regions import (
    infer_target_region_from_text,
    primary_target_region,
)
from research_automation.utils.urls import clean_url, url_hostname


def calculate_queue_score(
    relevance_score: int,
    editorial_quality: float | None,
) -> float:
    """Weight article relevance at exactly 90% and source quality at 10%."""

    relevance_component = relevance_score / 5
    source_component = editorial_quality / 10 if editorial_quality is not None else 0
    return round(100 * (0.90 * relevance_component + 0.10 * source_component), 2)


def evaluate_candidate_pool(
    articles: list[Article],
    *,
    deficits: dict[str, int],
    settings: Settings,
    enrich: Callable[[Article], EnrichedArticle] | None,
    now: datetime,
    excluded_urls: Iterable[str] = (),
    already_shortlisted: dict[str, int] | None = None,
    phase_ceiling_per_region: int | None = None,
    first_batch_size: int | None = None,
    stop_when_qualified: bool = True,
) -> CandidateEvaluation:
    """Evaluate an order-independent pool, scoring only bounded regional shortlists."""

    evaluation = CandidateEvaluation()
    excluded = {clean_url(url) for url in excluded_urls if clean_url(url)}
    prepared: dict[str, list[CandidateResult]] = defaultdict(list)
    run_urls: set[str] = set()

    # Stable metadata ordering means neither feed nor thread completion order is meaningful.
    for article in sorted(articles, key=_candidate_identity_sort):
        result = _prepare_candidate(article, settings=settings, now=now)
        if result.rejection_reason:
            evaluation.reject(result, result.rejection_reason)
            continue
        if article.canonical_url in excluded or article.canonical_url in run_urls:
            evaluation.reject(result, "duplicate URL")
            continue
        run_urls.add(article.canonical_url)
        if deficits.get(result.target_region or "", 0) <= 0:
            evaluation.reject(result, "regional target already complete")
            continue
        prepared[result.target_region or ""].append(result)

    prior_shortlist_counts = dict(already_shortlisted or {})
    for region, candidates in prepared.items():
        all_ordered = _source_diverse_shortlist(candidates)
        absolute_ceiling = min(
            settings.article_shortlist_max_per_region,
            phase_ceiling_per_region
            if phase_ceiling_per_region is not None
            else settings.article_shortlist_max_per_region,
        )
        score_budget = max(
            0,
            absolute_ceiling - prior_shortlist_counts.get(region, 0),
        )
        ordered = all_ordered[:score_budget]
        initial_count = min(
            first_batch_size
            if first_batch_size is not None
            else settings.article_shortlist_initial_per_region,
            len(ordered),
        )
        cursor = 0
        qualified = 0
        while cursor < len(ordered):
            batch_size = initial_count if cursor == 0 else min(2, len(ordered) - cursor)
            if batch_size <= 0:
                break
            batch = ordered[cursor : cursor + batch_size]
            cursor += batch_size
            evaluation.shortlisted_counts[region] = (
                evaluation.shortlisted_counts.get(region, 0) + len(batch)
            )
            for result in batch:
                if enrich is None:
                    evaluation.reject(result, "enrichment disabled")
                    continue
                try:
                    enriched = enrich(result.article)
                except Exception as exc:
                    evaluation.reject(result, f"enrichment failed: {exc}")
                    continue
                result.enrichment = enriched
                evaluation.enriched_counts[region] = (
                    evaluation.enriched_counts.get(region, 0) + 1
                )
                required_score = (
                    settings.minimum_article_relevance_score
                    if result.article.source_page_id
                    else 5
                )
                if enriched.relevance_score < required_score:
                    evaluation.reject(
                        result,
                        f"relevance below {required_score}",
                    )
                    continue
                result.queue_score = calculate_queue_score(
                    enriched.relevance_score,
                    result.source_quality,
                )
                result.selection_reason = (
                    f"{region} quota; relevance {enriched.relevance_score}/5; "
                    f"source quality {_quality_label(result.source_quality)}; "
                    f"queue score {result.queue_score:.2f}"
                )
                evaluation.results.append(result)
                qualified += 1
            if stop_when_qualified and qualified >= deficits.get(region, 0):
                break

        # Valid candidates outside the bounded LLM shortlist are reported, not silently lost.
        for result in ordered[cursor:]:
            evaluation.reject(result, "shortlist deferred")
        overflow_reason = (
            "shortlist deferred"
            if absolute_ceiling < settings.article_shortlist_max_per_region
            else "shortlist ceiling"
        )
        for result in all_ordered[score_budget:]:
            evaluation.reject(result, overflow_reason)

    return evaluation


def _prepare_candidate(
    article: Article,
    *,
    settings: Settings,
    now: datetime,
) -> CandidateResult:
    article.canonical_url = clean_url(article.canonical_url or article.url)
    article.url = clean_url(article.url or article.canonical_url)
    article.publisher_key = article.publisher_key or article.source_page_id or url_hostname(
        article.canonical_url
    )
    article.url_hash = build_url_hash(article.canonical_url) if article.canonical_url else ""
    article.content_hash = build_content_hash(article.title, article.source_name)
    source_quality = article.source_editorial_quality
    target_region = infer_target_region_from_text(f"{article.title}\n{article.snippet}")
    target_region = target_region or primary_target_region(article.region)
    if target_region:
        article.region = [target_region]

    result = CandidateResult(
        article=article,
        enrichment=None,
        target_region=target_region,
        source_quality=source_quality,
    )
    if not article.canonical_url or not url_hostname(article.canonical_url):
        result.rejection_reason = "no usable URL"
        return result
    if not _meaningful_title(article.title):
        result.rejection_reason = "no meaningful title"
        return result
    if article.published_date is None:
        result.rejection_reason = "unknown publication date"
        return result
    published = _aware_utc(article.published_date)
    if published < _aware_utc(now) - timedelta(days=settings.article_freshness_days):
        result.rejection_reason = "outside freshness window"
        return result
    matched_topics = matched_company_topics(article, settings.discovery_topics)
    if not matched_topics:
        result.rejection_reason = "no company-topic match"
        return result
    result.matched_topics = matched_topics
    if not article_has_interest_geography(article):
        result.rejection_reason = "outside geographic mandate"
        return result
    if not target_region:
        result.rejection_reason = "no exact target region"
        return result
    return result


def _source_diverse_shortlist(results: list[CandidateResult]) -> list[CandidateResult]:
    buckets: dict[str, deque[CandidateResult]] = defaultdict(deque)
    for result in sorted(results, key=_metadata_rank_sort):
        buckets[result.article.publisher_key].append(result)
    publisher_order = sorted(
        buckets,
        key=lambda key: _metadata_rank_sort(buckets[key][0]),
    )
    diversified: list[CandidateResult] = []
    while publisher_order:
        next_round: list[str] = []
        for key in publisher_order:
            diversified.append(buckets[key].popleft())
            if buckets[key]:
                next_round.append(key)
        publisher_order = next_round
    return diversified


def _metadata_rank_sort(result: CandidateResult) -> tuple:
    article = result.article
    return (
        -(_aware_utc(article.published_date).timestamp() if article.published_date else 0),
        -min(len(article.snippet.strip()), 500),
        -len(result.matched_topics),
        article.source_page_id == "",
        -(result.source_quality or 0),
        article.canonical_url,
    )


def _candidate_identity_sort(article: Article) -> tuple:
    return (
        clean_url(article.canonical_url or article.url),
        article.source_page_id == "",
        -(article.source_editorial_quality or 0),
        -(_aware_utc(article.published_date).timestamp() if article.published_date else 0),
        article.source_page_id,
        article.title.casefold(),
    )


def _meaningful_title(title: str) -> bool:
    words = [word for word in title.strip().split() if any(char.isalnum() for char in word)]
    return len(words) >= 3 and len(title.strip()) >= 12


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _quality_label(value: float | None) -> str:
    return "unscored" if value is None else f"{value:g}/10"

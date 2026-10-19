"""Metadata classification and bounded enrichment for the opt-in Luna path."""

from __future__ import annotations

from collections import Counter
from datetime import UTC
import logging

from research_automation.models.candidate import CandidateEvaluation, CandidateResult
from research_automation.pipeline.article_classification import prepare_classification_inputs
from research_automation.pipeline.article_retrieval import apply_retrieval_result
from research_automation.pipeline.candidate_ranking import (
    _editorial_significance, _is_self_published, _refresh_article_identity,
    calculate_queue_score,
)
from research_automation.pipeline.selection import probable_same_event
from research_automation.utils.regions import TARGET_REGION_ORDER
from research_automation.utils.urls import clean_url

logger = logging.getLogger(__name__)


def classify_luna_candidates(
    articles, *, settings, classifier, now, excluded_urls=(), seen_url_hashes=(), phase="rss",
) -> CandidateEvaluation:
    """Classify the entire objectively eligible pool before allocating any enrichment.

    A missing classification is an operational failure, never an Irrelevant vote.
    Such articles stay available for bounded detailed assessment with no invented
    score or geography. Their failure also remains visible in the audit.
    """

    ordered = sorted(articles, key=lambda a: (
        a.canonical_url or a.url, not bool(a.source_page_id),
        -(a.source_editorial_quality or 0), a.title.casefold(),
    ))
    prepared = prepare_classification_inputs(
        ordered, now=now, freshness_days=settings.article_freshness_days,
        excluded_urls=excluded_urls, seen_url_hashes=seen_url_hashes,
    )
    exclusions = {entry.input_index: entry for entry in prepared.excluded}
    accepted = iter(prepared.inputs)
    evaluation = CandidateEvaluation()
    by_id = {}
    for index, article in enumerate(ordered):
        exclusion = exclusions.get(index)
        metadata = None if exclusion else next(accepted)
        result = CandidateResult(
            article, None, None, source_quality=article.source_editorial_quality,
            candidate_id=exclusion.article_id if exclusion else metadata.article_id,
            phase=phase, source_region_hints=list(article.region),
            required_relevance_score=(settings.minimum_article_relevance_score if article.source_page_id else 5),
        )
        if exclusion:
            result.objective_cleanup_reason = exclusion.reason
            evaluation.reject(result, exclusion.reason)
            continue
        _refresh_article_identity(article)
        evaluation.results.append(result)
        by_id[result.candidate_id] = result

    if classifier is None:
        for result in by_id.values():
            _reject(evaluation, result, "LLM assessment disabled")
        return evaluation
    if not prepared.inputs:
        return evaluation
    # classify() returns only after ALL batches and their bounded recoveries finish.
    report = classifier.classify(prepared.inputs)
    evaluation.classification_reports.append(report)
    attempted = {article_id for request in report.requests for article_id in request.article_ids}
    for outcome in report.outcomes:
        result = by_id[outcome.article_id]
        result.classification_attempted = outcome.article_id in attempted
        result.classification = outcome.classification
        result.classification_error = outcome.error
        classification = outcome.classification
        if classification is None:
            result.region_assignment_basis = "classification unresolved; requires evidence assessment"
        elif classification.decision == "Irrelevant":
            _reject(evaluation, result, "Luna classified irrelevant")
        else:
            result.target_region = (
                classification.assigned_region
                if classification.assigned_region in TARGET_REGION_ORDER else None
            )
            result.region_assignment_basis = "Luna metadata event geography; source hints are not proof"
    return evaluation


def enrich_luna_candidates(
    evaluation, *, settings, deficits, budget, enrich, retrieve, excluded_urls,
    attempted_urls, weekly_state, enough_candidates=None, positive_only=False,
    quality_backfill=False,
) -> int:
    """Allocate from merged classifications; count failed calls against the budget."""

    pending = [
        result for result in evaluation.results
        if not result.rejection_reason and not result.enrichment_attempted
        and (not positive_only or result.classification is not None)
    ]
    available = []
    for result in pending:
        if any(probable_same_event(result.article.title, title) for title in weekly_state.existing_titles):
            _reject(evaluation, result, "existing event")
        else:
            available.append(result)
    for rank, result in enumerate(sorted(available, key=_rank), start=1):
        result.metadata_rank = rank
    # Diversity is soft and persists across RSS/discovery/adaptive batches.
    publishers = Counter(weekly_state.publisher_counts)
    publishers.update(result.article.publisher_key for result in evaluation.results if result.enrichment_attempted)
    ordered = _allocate(
        available, deficits, budget, publishers=publishers,
        quality_backfill=quality_backfill,
    )
    used = 0
    for rank, result in enumerate(ordered, start=1):
        result.allocation_rank = rank
        if used >= budget or (enough_candidates is not None and enough_candidates()):
            break
        article = result.article
        # Never pass a discovery query or publisher country as factual geography.
        article.region = [result.target_region] if result.target_region else []
        original = article.canonical_url
        if retrieve is not None:
            try:
                apply_retrieval_result(article, retrieve(article))
            except Exception:
                article.evidence_retrieval_status = "fetch_failed"
            _refresh_article_identity(article)
        duplicate_url = article.canonical_url in excluded_urls or article.canonical_url in attempted_urls
        if article.google_news_resolution.get("status") == "resolved":
            # Test prior identity first, then retain every attempted alias, even
            # when this publisher URL is already processed or self-published.
            attempted_urls.update((original, clean_url(article.url), article.canonical_url))
        if duplicate_url:
            _reject(evaluation, result, "duplicate URL")
            continue
        if _is_self_published(article):
            _reject(evaluation, result, "self-published content after URL resolution")
            continue
        result.shortlisted = True
        result.enrichment_attempted = True
        used += 1
        region = result.target_region or "Unassigned"
        evaluation.shortlisted_counts[region] = evaluation.shortlisted_counts.get(region, 0) + 1
        attempted_urls.update((original, clean_url(article.url), article.canonical_url))
        try:
            enriched = enrich(article)
        except Exception:
            logger.warning("Luna detailed enrichment failed for candidate %s", result.candidate_id)
            _reject(evaluation, result, "enrichment failed: provider error")
            continue
        result.enrichment = enriched
        evaluation.enriched_counts[region] = evaluation.enriched_counts.get(region, 0) + 1
        if result.editorial_rejection_reason:
            _reject(evaluation, result, result.editorial_rejection_reason)
            continue
        if enriched.relevance_score < result.required_relevance_score:
            _reject(evaluation, result, f"relevance below {result.required_relevance_score}")
            # Keep the strict rejection. Only a possible fallback needs final
            # geography/score preparation; no additional retrieval or model call.
            if not (article.source_page_id and enriched.relevance_score >= 3
                    and _editorial_significance(enriched) >= 3):
                continue
        if result.target_region is None:
            regions = set(enriched.region)
            if len(regions) != 1 or not regions.issubset(TARGET_REGION_ORDER):
                if not result.rejection_reason:
                    _reject(evaluation, result, "geography unresolved after enrichment")
                continue
            result.target_region = next(iter(regions))
            result.region_assignment_basis = "Luna detailed evidence assessment resolved unclear metadata geography"
            article.region = [result.target_region]
        result.queue_score = calculate_queue_score(
            enriched.relevance_score, result.source_quality, _editorial_significance(enriched),
        )
        result.selection_reason = (
            f"{result.target_region} coverage; relevance {enriched.relevance_score}/5; "
            f"editorial significance {_editorial_significance(enriched)}/5; "
            f"publisher quality {result.source_quality if result.source_quality is not None else 'unscored'}; "
            f"queue score {result.queue_score:.2f}"
        )
    return used


def finish_luna_evaluation(evaluation, *, budget_exhausted, coverage_filled=True):
    """Make every unassessed article explicit without calling it irrelevant."""

    for result in evaluation.results:
        if not result.rejection_reason and not result.enrichment_attempted:
            reason = "enrichment budget exhausted" if budget_exhausted else (
                "assessment deferred; run coverage filled" if coverage_filled
                else "assessment deferred; no eligible backfill"
            )
            _reject(evaluation, result, reason)


def _rank(result):
    classification = result.classification
    published = result.article.published_date
    if published and published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return (
        {"Relevant": 0, "Borderline": 1}.get(classification.decision, 2) if classification else 2,
        -classification.relevance_score if classification else 0,
        -(result.source_quality or 0),
        -published.timestamp() if published else 0,
        result.article.canonical_url,
    )


def _allocate(candidates, deficits, budget, *, publishers=None, quality_backfill=False):
    """Provide regional opportunity initially; rank merged backfill by quality.

    Coverage reservations are opportunities, never per-region enrichment ceilings.
    Publisher round-robin carries previous attempt counts between batches;
    classifier decision/score, quality and freshness rank each publisher's turn.
    """

    remaining = list(candidates)
    ordered = []
    publishers = Counter(publishers or {})
    allocated = Counter()

    def rank(result):
        base = _rank(result)
        if quality_backfill:
            # Editorial tier leads; diversify within equal decision/score tiers.
            # Shortage is only a tie-break after quality and publication date.
            return (
                *base[:2], publishers[result.article.publisher_key], *base[2:-1],
                -int(deficits.get(result.target_region or "", 0) > 0), base[-1],
            )
        return (publishers[result.article.publisher_key], *base)

    while remaining:
        coverage_regions = [
            region for region in TARGET_REGION_ORDER
            if allocated[region] < 2 * deficits.get(region, 0)
            and any(result.target_region == region for result in remaining)
        ] if not quality_backfill and len(ordered) < budget else []
        if coverage_regions:
            region = min(coverage_regions, key=lambda r: (
                allocated[r] / deficits[r], TARGET_REGION_ORDER.index(r),
            ))
            pool = [result for result in remaining if result.target_region == region]
        else:
            pool = remaining
        best = min(pool, key=rank)
        ordered.append(best)
        allocated[best.target_region] += 1
        publishers[best.article.publisher_key] += 1
        remaining.remove(best)
    return ordered


def _reject(evaluation, result, reason):
    result.rejection_reason = reason
    evaluation.rejection_counts[reason] = evaluation.rejection_counts.get(reason, 0) + 1

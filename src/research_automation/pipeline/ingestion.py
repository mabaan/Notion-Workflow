"""End-to-end pool-wide ingestion orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Callable

from research_automation.clients.llm_client import LlmClient
from research_automation.clients.notion_client import NotionClient
from research_automation.config import Settings
from research_automation.models.candidate import CandidateEvaluation, CandidateResult
from research_automation.models.source import SourceAttempt
from research_automation.notion_schema import ARTICLE_QUEUE
from research_automation.pipeline.candidate_ranking import evaluate_candidate_pool
from research_automation.pipeline.collect import CollectionResult, collect_articles
from research_automation.pipeline.deduplicate import SeenArticleStore
from research_automation.pipeline.discovery import DiscoveryService
from research_automation.pipeline.notion_write import create_article_queue_page
from research_automation.pipeline.selection import (
    SelectionResult,
    WeeklyQueueState,
    load_weekly_queue_state,
    select_final_candidates,
)
from research_automation.pipeline.source_health import (
    select_due_sources,
    update_source_health,
)
from research_automation.pipeline.source_registry import load_active_sources
from research_automation.pipeline.weekly_pages import (
    ensure_current_weekly_pages,
    find_dataset_meeting_for_week,
)
from research_automation.utils.dates import current_workweek, utc_now
from research_automation.utils.regions import TARGET_REGION_ORDER, target_deficits

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionOptions:
    dry_run: bool = False
    no_enrich: bool = False
    all_sources: bool = False
    limit: int | None = None


@dataclass
class IngestionReport:
    existing_region_counts: dict[str, int]
    initial_deficits: dict[str, int]
    due_sources: list[str]
    skipped_sources: list[str]
    attempts: list[SourceAttempt]
    collected_count: int
    discovered_count: int
    evaluation: CandidateEvaluation
    selection: SelectionResult
    pages_created: int = 0
    page_errors: list[str] = field(default_factory=list)
    provider_requests: dict[str, int] = field(default_factory=dict)
    dry_run: bool = False


def run_ingestion(
    settings: Settings,
    options: IngestionOptions,
    *,
    notion=None,
    llm_client=None,
    collector: Callable[[list], CollectionResult] = collect_articles,
    discovery_factory: Callable[[Settings, list], DiscoveryService] = DiscoveryService,
    output: Callable[[str], None] = print,
) -> IngestionReport:
    """Evaluate the complete bounded pool before creating any Article Queue page."""

    settings.validate()
    if options.no_enrich and not options.dry_run:
        raise ValueError("--no-enrich is read-only and requires --dry-run")
    requested_limit = options.limit if options.limit is not None else settings.max_articles_per_run
    if requested_limit <= 0:
        raise ValueError("--limit must be greater than zero")
    run_limit = min(requested_limit, settings.max_articles_per_run)
    now = utc_now()
    workweek = current_workweek()
    notion = notion or NotionClient(token=settings.notion_token)

    sources = load_active_sources(notion, settings)
    due_sources = select_due_sources(sources, now, all_sources=options.all_sources)
    due_ids = {source.notion_page_id for source in due_sources}
    skipped_due = [
        source.name
        for source in sources
        if source.source_type == "Publisher" and source.notion_page_id not in due_ids
    ]

    dataset_meeting_page_id: str | None
    if options.dry_run:
        dataset = find_dataset_meeting_for_week(
            notion,
            settings,
            workweek,
        )
        dataset_meeting_page_id = dataset.get("id") if dataset else None
    else:
        dataset_meeting_page_id = ensure_current_weekly_pages(
            notion, settings, reference_date=workweek.start
        ).dataset_meeting_id

    weekly_state = load_weekly_queue_state(
        notion, settings, dataset_meeting_page_id
    )
    initial_deficits = target_deficits(
        weekly_state.region_counts, settings.weekly_region_targets
    )

    collection = collector(due_sources)
    if not options.dry_run:
        for attempt in collection.attempts:
            try:
                update_source_health(notion, attempt)
            except Exception:
                logger.exception("Failed to update source health for %s", attempt.source_name)

    store = SeenArticleStore(settings.seen_articles_path)
    excluded_urls = set(weekly_state.existing_urls)
    excluded_urls.update(
        str(record.get("canonical_url") or "") for record in store.records.values()
    )
    enrich_callable = (
        _enrichment_callable(settings, options, llm_client)
        if any(initial_deficits.values())
        else None
    )
    feed_evaluation = evaluate_candidate_pool(
        collection.articles,
        deficits=initial_deficits,
        settings=settings,
        enrich=enrich_callable,
        now=now,
        excluded_urls=excluded_urls,
        phase_ceiling_per_region=settings.article_shortlist_initial_per_region,
    )
    feed_selection = select_final_candidates(
        [result for result in feed_evaluation.results if result.eligible],
        weekly_state=weekly_state,
        targets=settings.weekly_region_targets,
        run_limit=run_limit,
        publisher_cap=settings.max_articles_per_publisher_per_week,
    )

    discovery = discovery_factory(settings, sources)
    expansion_evaluation = CandidateEvaluation()
    discovered = []
    if (
        any(feed_selection.shortages.values())
        and len(feed_selection.winners) < run_limit
        and not options.no_enrich
    ):
        known_hashes = set(store.records)
        known_hashes.update(
            result.article.url_hash for result in feed_evaluation.results
            if result.article.url_hash
        )
        discovered = discovery.discover_articles(
            feed_selection.shortages,
            max_per_region=settings.article_shortlist_max_per_region,
            excluded_hashes=known_hashes,
        )
        deferred_feed_articles = [
            result.article
            for result in feed_evaluation.results
            if result.rejection_reason == "shortlist deferred"
            and feed_selection.shortages.get(result.target_region or "", 0) > 0
        ]
        expansion_pool = [*deferred_feed_articles, *discovered]
        if expansion_pool:
            expansion_evaluation = evaluate_candidate_pool(
                expansion_pool,
                deficits=feed_selection.shortages,
                settings=settings,
                enrich=enrich_callable,
                now=now,
                excluded_urls=excluded_urls,
                already_shortlisted=feed_evaluation.shortlisted_counts,
                first_batch_size=2,
                stop_when_qualified=False,
            )

    evaluation = _merge_evaluations(feed_evaluation, expansion_evaluation)
    selection = select_final_candidates(
        [result for result in evaluation.results if result.eligible],
        weekly_state=weekly_state,
        targets=settings.weekly_region_targets,
        run_limit=run_limit,
        publisher_cap=settings.max_articles_per_publisher_per_week,
    )

    all_attempts = [*collection.attempts, *discovery.attempts]
    if not options.dry_run:
        for attempt in discovery.attempts:
            try:
                update_source_health(notion, attempt)
            except Exception:
                logger.exception("Failed to update provider health for %s", attempt.source_name)

    pages_created = 0
    page_errors: list[str] = []
    actual_state = _copy_weekly_state(weekly_state)
    if not options.dry_run:
        article_database = notion.retrieve_database(settings.notion_article_queue_database_id)
        article_property_schema = article_database.get("properties", {})
        available_properties = set(article_property_schema)
        if article_property_schema.get(ARTICLE_QUEUE["queue_score"], {}).get("type") != "number":
            available_properties.discard(ARTICLE_QUEUE["queue_score"])
        if article_property_schema.get(ARTICLE_QUEUE["selection_reason"], {}).get("type") != "rich_text":
            available_properties.discard(ARTICLE_QUEUE["selection_reason"])
        for optional_name in (
            ARTICLE_QUEUE["queue_score"],
            ARTICLE_QUEUE["selection_reason"],
        ):
            if optional_name not in available_properties:
                logger.info(
                    "Article Queue has no %s property; value will remain in run logs.",
                    optional_name,
                )
        for winner in selection.winners:
            try:
                page = create_article_queue_page(
                    notion,
                    settings.notion_article_queue_database_id,
                    winner.article,
                    dataset_meeting_page_id,
                    enriched=winner.enrichment,
                    processed_at=now,
                    queue_score=winner.queue_score,
                    selection_reason=winner.selection_reason,
                    available_properties=available_properties,
                )
            except Exception as exc:
                message = f"{winner.article.title}: {exc}"
                page_errors.append(message)
                logger.exception("Failed to create Article Queue winner %s", winner.article.title)
                continue
            pages_created += 1
            _add_winner_to_state(actual_state, winner)
            store.record(
                url_hash=winner.article.url_hash,
                title=winner.article.title,
                canonical_url=winner.article.canonical_url,
                source=winner.article.source_name,
                notion_page_id=page["id"],
                created_at=now.isoformat(),
            )
        selection.final_state = actual_state
        selection.shortages = target_deficits(
            actual_state.region_counts, settings.weekly_region_targets
        )

    report = IngestionReport(
        existing_region_counts=dict(weekly_state.region_counts),
        initial_deficits=initial_deficits,
        due_sources=[source.name for source in due_sources],
        skipped_sources=[*skipped_due, *collection.skipped_sources],
        attempts=all_attempts,
        collected_count=len(collection.articles),
        discovered_count=len(discovered),
        evaluation=evaluation,
        selection=selection,
        pages_created=pages_created,
        page_errors=page_errors,
        provider_requests={
            "brave": discovery.budget.brave_requests,
            "newsapi": discovery.budget.newsapi_requests,
        },
        dry_run=options.dry_run,
    )
    print_ingestion_report(report, output=output)
    return report


def print_ingestion_report(
    report: IngestionReport,
    *,
    output: Callable[[str], None] = print,
) -> None:
    """Print the dry-run/live audit trail required for safe operation."""

    output("Existing weekly counts: " + _format_regions(report.existing_region_counts))
    output("Regional deficits: " + _format_regions(report.initial_deficits))
    output("Due sources: " + (", ".join(report.due_sources) or "none"))
    output("Skipped sources: " + (", ".join(report.skipped_sources) or "none"))
    for attempt in report.attempts:
        detail = f"; error={attempt.error}" if attempt.error else ""
        output(
            f"Source outcome: {attempt.source_name}={attempt.outcome}; "
            f"articles={attempt.article_count}; duration_ms={attempt.duration_ms}{detail}"
        )
    output(f"Number collected from due feeds: {report.collected_count}")
    output(f"Number collected from discovery: {report.discovered_count}")
    for reason, count in sorted(report.evaluation.rejection_counts.items()):
        output(f"Rejected [{reason}]: {count}")
    for reason, count in sorted(report.selection.rejected_by_constraint.items()):
        output(f"Constraint rejected [{reason}]: {count}")
    output(
        "Number shortlisted: "
        + _format_regions(report.evaluation.shortlisted_counts)
    )
    output("Number enriched: " + _format_regions(report.evaluation.enriched_counts))
    prefix = "Would create" if report.dry_run else "Created/winner"
    for rank, winner in enumerate(report.selection.winners, start=1):
        enriched = winner.enrichment
        output(
            f"{prefix} #{rank}: region={winner.target_region}; publisher={winner.article.source_name}; "
            f"relevance={enriched.relevance_score if enriched else 'n/a'}; "
            f"source_rating={winner.source_quality if winner.source_quality is not None else 'unscored'}; "
            f"queue_score={winner.queue_score:.2f}; title={winner.article.title}"
        )
    output(
        "Publisher counts: "
        + ", ".join(
            f"{key}={count}"
            for key, count in sorted(report.selection.final_state.publisher_counts.items())
        )
        or "Publisher counts: none"
    )
    output("Remaining regional shortages: " + _format_regions(report.selection.shortages))
    output(
        "Provider request counts: "
        + ", ".join(
            f"{name}={count}" for name, count in report.provider_requests.items()
        )
    )
    if report.dry_run:
        output("Notion writes: 0 (dry-run)")
    else:
        output(f"Article Queue pages created: {report.pages_created}")
    for error in report.page_errors:
        output(f"Page creation error: {error}")


def _enrichment_callable(settings, options, llm_client):
    if options.no_enrich:
        return None
    client = llm_client or LlmClient(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        prompt_directory=settings.prompt_directory,
        company_topics=settings.discovery_topics,
    )
    return client.enrich_article


def _merge_evaluations(*evaluations: CandidateEvaluation) -> CandidateEvaluation:
    merged = CandidateEvaluation()
    for evaluation in evaluations:
        merged.results.extend(evaluation.results)
        for target, source in (
            (merged.rejection_counts, evaluation.rejection_counts),
            (merged.shortlisted_counts, evaluation.shortlisted_counts),
            (merged.enriched_counts, evaluation.enriched_counts),
        ):
            for key, value in source.items():
                target[key] = target.get(key, 0) + value
    return merged


def _copy_weekly_state(state: WeeklyQueueState) -> WeeklyQueueState:
    return WeeklyQueueState(
        region_counts=dict(state.region_counts),
        publisher_counts=dict(state.publisher_counts),
        existing_urls=set(state.existing_urls),
        existing_titles=list(state.existing_titles),
    )


def _add_winner_to_state(state: WeeklyQueueState, winner: CandidateResult) -> None:
    region = winner.target_region
    if region:
        state.region_counts[region] = state.region_counts.get(region, 0) + 1
    key = winner.article.publisher_key
    state.publisher_counts[key] = state.publisher_counts.get(key, 0) + 1
    state.existing_urls.add(winner.article.canonical_url)
    state.existing_titles.append(winner.article.title)


def _format_regions(values: dict[str, int]) -> str:
    return ", ".join(f"{region}={values.get(region, 0)}" for region in TARGET_REGION_ORDER)

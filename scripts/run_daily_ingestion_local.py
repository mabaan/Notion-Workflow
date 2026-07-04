"""Run the local daily ingestion workflow."""

from __future__ import annotations

import argparse
import logging

from research_automation.clients.llm_client import LlmClient
from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings
from research_automation.logging_config import configure_logging
from research_automation.pipeline.collect import collect_articles
from research_automation.pipeline.deduplicate import SeenArticleStore
from research_automation.pipeline.discovery import (
    DiscoveryService,
    count_weekly_region_coverage,
    select_feed_articles_for_run,
)
from research_automation.pipeline.enrich import enrich_article
from research_automation.pipeline.notion_write import (
    create_article_queue_page,
    update_article_enrichment,
    update_article_error,
    update_source_last_checked,
)
from research_automation.pipeline.source_registry import load_active_sources
from research_automation.pipeline.weekly_pages import ensure_current_weekly_pages
from research_automation.utils.dates import utc_now
from research_automation.utils.hashing import build_content_hash, build_url_hash
from research_automation.utils.urls import clean_url

logger = logging.getLogger(__name__)


def parse_args(default_limit: int) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Notion.")
    parser.add_argument(
        "--limit",
        type=int,
        default=default_limit,
        help="Maximum number of Article Queue pages to create.",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Create Article Queue pages without calling OpenAI.",
    )
    return parser.parse_args()


def main() -> None:
    settings = load_settings()
    args = parse_args(settings.max_articles_per_run)
    configure_logging(settings.log_level)

    notion = NotionClient(token=settings.notion_token)
    sources = load_active_sources(notion, settings)
    collection = collect_articles(sources)
    store = SeenArticleStore(settings.seen_articles_path)
    existing_article_pages = notion.query_database(settings.notion_article_queue_database_id)
    existing_article_page_ids = {page.get("id", "") for page in existing_article_pages if page.get("id")}
    removed_dedupe_records = store.prune_missing_pages(
        existing_article_page_ids,
        persist=not args.dry_run,
    )

    llm_client: LlmClient | None = None
    dataset_meeting_page_id: str | None = None
    weekly_region_counts = {
        region: 0 for region in settings.weekly_region_targets
    }
    if not args.dry_run:
        weekly_pages = ensure_current_weekly_pages(notion, settings)
        dataset_meeting_page_id = weekly_pages.dataset_meeting_id
        weekly_region_counts = count_weekly_region_coverage(
            notion,
            settings,
            dataset_meeting_page_id,
        )
        if not args.no_enrich:
            llm_client = LlmClient(
                provider=settings.llm_provider,
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                prompt_directory=settings.prompt_directory,
            )

    stats = {
        "sources_checked": len(sources),
        "articles_found": len(collection.articles),
        "duplicates_skipped": 0,
        "pages_created": 0,
        "pages_enriched": 0,
        "errors": len(collection.source_errors),
        "skipped_by_limit": 0,
        "would_create": 0,
        "fallback_articles_selected": 0,
        "stale_dedupe_records_removed": removed_dedupe_records,
    }

    logger.info("Job started: %s sources", len(sources))

    run_seen: set[str] = set()
    prepared_articles = []
    for article in collection.articles:
        article.canonical_url = clean_url(article.canonical_url or article.url)
        if not article.canonical_url:
            stats["errors"] += 1
            logger.warning("Skipping article with no usable URL: %s", article.title)
            continue

        article.url_hash = build_url_hash(article.canonical_url)
        article.content_hash = build_content_hash(article.title, article.source_name)

        if article.url_hash in run_seen or store.contains(article.url_hash):
            stats["duplicates_skipped"] += 1
            continue

        run_seen.add(article.url_hash)
        prepared_articles.append(article)

    selected_feed_articles, remaining_deficits = select_feed_articles_for_run(
        prepared_articles,
        current_counts=weekly_region_counts,
        target_counts=settings.weekly_region_targets,
        limit=args.limit,
    )
    selected_hashes = {article.url_hash for article in selected_feed_articles}
    discovery = DiscoveryService(settings, sources)
    top_up_articles = discovery.top_up_articles(
        dict(remaining_deficits),
        limit=max(0, args.limit - len(selected_feed_articles)),
        excluded_hashes=set(store.records) | run_seen,
    )
    stats["fallback_articles_selected"] = len(top_up_articles)

    remaining_feed_articles = [
        article
        for article in prepared_articles
        if article.url_hash not in selected_hashes
    ]
    selected_articles = [*selected_feed_articles, *top_up_articles]
    if len(selected_articles) < args.limit:
        backfill_slots = args.limit - len(selected_articles)
        selected_articles.extend(remaining_feed_articles[:backfill_slots])

    stats["skipped_by_limit"] = max(0, len(prepared_articles) - len(selected_articles))

    for article in selected_articles:
        if args.dry_run:
            stats["would_create"] += 1
            logger.info("Dry run: would create %s", article.title)
            continue

        try:
            page = create_article_queue_page(
                notion,
                settings.notion_article_queue_database_id,
                article,
                dataset_meeting_page_id,
            )
            stats["pages_created"] += 1
            store.record(
                url_hash=article.url_hash,
                title=article.title,
                canonical_url=article.canonical_url,
                source=article.source_name,
                notion_page_id=page["id"],
                created_at=utc_now().isoformat(),
            )
        except Exception:
            stats["errors"] += 1
            logger.exception("Failed to create Article Queue page for %s", article.title)
            continue

        if llm_client is None:
            continue

        try:
            enriched = enrich_article(article, llm_client)
            update_article_enrichment(
                notion,
                page["id"],
                enriched,
                utc_now(),
                base_regions=article.region,
            )
            stats["pages_enriched"] += 1
        except Exception as exc:
            stats["errors"] += 1
            logger.exception("Failed to enrich article %s", article.title)
            update_article_error(notion, page["id"], str(exc))

    checked_at_iso = utc_now().isoformat()
    if not args.dry_run:
        for source in sources:
            update_source_last_checked(notion, source.notion_page_id, checked_at_iso)

    logger.info("Job finished: %s pages created", stats["pages_created"])
    print(f"Sources checked: {stats['sources_checked']}")
    print(f"Articles found: {stats['articles_found']}")
    print(f"Duplicates skipped: {stats['duplicates_skipped']}")
    print(f"Pages created: {stats['pages_created']}")
    print(f"Pages enriched: {stats['pages_enriched']}")
    if args.dry_run:
        print(f"Would create: {stats['would_create']}")
    print(f"Fallback articles selected: {stats['fallback_articles_selected']}")
    print(f"Stale dedupe records removed: {stats['stale_dedupe_records_removed']}")
    print(f"Errors: {stats['errors']}")
    print(f"Skipped by limit: {stats['skipped_by_limit']}")


if __name__ == "__main__":
    main()

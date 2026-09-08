"""Run pool-wide Article Queue selection locally."""

from __future__ import annotations

import argparse

from research_automation.config import load_settings
from research_automation.logging_config import (
    configure_console_encoding,
    configure_logging,
)
from research_automation.pipeline.ingestion import IngestionOptions, run_ingestion


def parse_args(default_limit: int) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without writes.")
    parser.add_argument(
        "--limit",
        type=int,
        default=default_limit,
        help="Requested creation ceiling; never exceeds MAX_ARTICLES_PER_RUN.",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Inspect deterministic gates without LLM calls; requires --dry-run.",
    )
    parser.add_argument(
        "--all-sources",
        action="store_true",
        help="Bypass publisher due scheduling for a manual health check.",
    )
    args = parser.parse_args()
    if args.no_enrich and not args.dry_run:
        parser.error("--no-enrich requires --dry-run and can never write live pages")
    return args


def main() -> None:
    configure_console_encoding()
    settings = load_settings()
    args = parse_args(settings.max_articles_per_run)
    configure_logging(settings.log_level)
    run_ingestion(
        settings,
        IngestionOptions(
            dry_run=args.dry_run,
            no_enrich=args.no_enrich,
            all_sources=args.all_sources,
            limit=args.limit,
        ),
    )


if __name__ == "__main__":
    main()

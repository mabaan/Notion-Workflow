"""Generate weekly Newsletter and Social Media drafts from approved articles."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from research_automation.clients.llm_client import LlmClient
from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings
from research_automation.logging_config import configure_logging
from research_automation.models.article import Article
from research_automation.models.draft import DraftArticle
from research_automation.pipeline.article_retrieval import (
    ArticleRetrievalResult,
    ArticleRetriever,
    apply_retrieval_result,
)
from research_automation.pipeline.draft import (
    format_newsletter_articles_for_prompt,
    format_social_articles_for_prompt,
    load_weekly_draft_articles,
    select_featured_articles,
)
from research_automation.pipeline.images import (
    ArticleImageResolver,
    inject_story_images,
)
from research_automation.pipeline.draft_validation import (
    print_validation_warnings,
    validate_newsletter_draft,
    validate_newsletter_images,
    validate_social_draft,
)
from research_automation.pipeline.notion_write import (
    mark_newsletter_ready_for_review,
    mark_social_media_ready,
    replace_generated_section,
)
from research_automation.pipeline.weekly_pages import ensure_current_weekly_pages
from research_automation.pipeline.weekly_pages import find_dataset_meeting_for_week
from research_automation.utils.dates import current_workweek
from research_automation.utils.urls import clean_url, is_google_news_url, url_hostname


@dataclass(frozen=True)
class EvidenceRefreshRecord:
    """Read-only audit details for one preview article refresh."""

    title: str
    original_url: str
    retrieval_url: str
    resolved_url: str
    url_resolution_status: str
    evidence_retrieval_status: str
    factual_points: tuple[str, ...]
    source_limitation: str
    enrichment_error: str = ""

    @property
    def full_article_enriched(self) -> bool:
        return (
            self.evidence_retrieval_status.casefold() == "extracted"
            and bool(self.factual_points)
            and not self.enrichment_error
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Generate local drafts without Notion writes or image resolution.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".preview") / "weekly_drafts",
        help="Base directory for preview files (used only with --preview).",
    )
    parser.add_argument(
        "--refresh-evidence",
        action="store_true",
        help=(
            "In preview mode, retrieve and enrich selected articles in memory before "
            "drafting."
        ),
    )
    parser.add_argument(
        "--publisher-url-override",
        action="append",
        default=[],
        metavar="TITLE_MATCH=URL",
        help=(
            "Verified publisher URL for a selected preview story. May be repeated and "
            "is used only with --preview --refresh-evidence."
        ),
    )
    args = parser.parse_args(argv)
    if args.refresh_evidence and not args.preview:
        parser.error("--refresh-evidence requires --preview")
    if args.publisher_url_override and not args.refresh_evidence:
        parser.error("--publisher-url-override requires --preview --refresh-evidence")
    return args


def main(argv: list[str] | None = None) -> None:
    settings = load_settings()
    args = parse_args(argv)
    configure_logging(settings.log_level)
    notion = NotionClient(token=settings.notion_token)

    if args.preview:
        _run_preview(
            notion,
            settings,
            args.output_dir,
            refresh_evidence=args.refresh_evidence,
            publisher_url_overrides=_parse_publisher_url_overrides(
                args.publisher_url_override
            ),
        )
        return

    weekly_pages = ensure_current_weekly_pages(notion, settings)
    newsletter_articles = load_weekly_draft_articles(
        notion,
        settings,
        weekly_pages.dataset_meeting_id,
        ["Use in Newsletter"],
    )
    social_articles = load_weekly_draft_articles(
        notion,
        settings,
        weekly_pages.dataset_meeting_id,
        ["Use in Newsletter", "SNS Only"],
    )
    newsletter_articles = select_featured_articles(newsletter_articles, max_items=3)
    social_articles = select_featured_articles(social_articles, max_items=3)

    if not newsletter_articles and not social_articles:
        print("No approved articles found for the current week. No drafts were generated.")
        return

    llm_client = LlmClient(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        prompt_directory=settings.prompt_directory,
        company_topics=settings.discovery_topics,
    )

    week_start = weekly_pages.week.start.isoformat()
    week_end = weekly_pages.week.end.isoformat()
    image_resolver = ArticleImageResolver(settings)

    if newsletter_articles:
        image_resolver.resolve_articles(newsletter_articles)
        newsletter_draft = llm_client.generate_newsletter_draft(
            week_start,
            week_end,
            format_newsletter_articles_for_prompt(newsletter_articles),
        )
        newsletter_draft = inject_story_images(newsletter_draft, newsletter_articles)
        newsletter_warnings = [
            *validate_newsletter_draft(newsletter_draft, newsletter_articles),
            *validate_newsletter_images(newsletter_articles),
        ]
        print_validation_warnings("Newsletter", newsletter_warnings)
        replace_generated_section(
            notion,
            weekly_pages.newsletter_id,
            "newsletter_draft",
            newsletter_draft,
        )
        mark_newsletter_ready_for_review(notion, weekly_pages.newsletter_id)
        print(f"Newsletter draft updated with {len(newsletter_articles)} approved articles.")
    else:
        print("No newsletter-approved articles found for the current week.")

    if social_articles:
        social_draft = llm_client.generate_social_media_draft(
            week_start,
            week_end,
            format_social_articles_for_prompt(social_articles),
        )
        social_warnings = validate_social_draft(social_draft, social_articles)
        print_validation_warnings("SNS", social_warnings)
        replace_generated_section(
            notion,
            weekly_pages.social_media_id,
            "social_media_draft",
            social_draft,
        )
        mark_social_media_ready(notion, weekly_pages.social_media_id)
        print(f"Social media draft updated with {len(social_articles)} approved articles.")
    else:
        print("No social-media-approved articles found for the current week.")


def _run_preview(
    notion: NotionClient,
    settings,
    output_dir: Path,
    *,
    refresh_evidence: bool = False,
    publisher_url_overrides: dict[str, str] | None = None,
    output=print,
) -> list[Path]:
    """Generate read-only weekly drafts and save them outside ingestion state."""

    week = current_workweek()
    preview_dir = output_dir / f"{week.start.isoformat()}_to_{week.end.isoformat()}"
    if refresh_evidence:
        preview_dir = preview_dir / "evidence_refresh"
    preview_dir.mkdir(parents=True, exist_ok=True)
    summary_path = preview_dir / (
        "evidence_report.md" if refresh_evidence else "preview_summary.md"
    )
    created_paths: list[Path] = []

    dataset_page = find_dataset_meeting_for_week(notion, settings, week)
    if dataset_page is None:
        summary_path.write_text(
            "\n".join(
                [
                    "# Weekly Draft Preview",
                    "",
                    f"Week: {week.start.isoformat()} to {week.end.isoformat()}",
                    "",
                    "No existing Dataset Meeting page was found for this week.",
                    "No Article Queue records or LLM drafts were evaluated.",
                    "No Notion pages or local ingestion state were modified.",
                ]
            ),
            encoding="utf-8",
        )
        output("Preview incomplete: no existing Dataset Meeting page was found.")
        output(f"Preview summary: {summary_path.resolve()}")
        return [summary_path]

    dataset_id = str(dataset_page.get("id") or "")
    newsletter_articles = select_featured_articles(
        load_weekly_draft_articles(
            notion,
            settings,
            dataset_id,
            ["Use in Newsletter"],
        ),
        max_items=3,
    )
    social_articles = select_featured_articles(
        load_weekly_draft_articles(
            notion,
            settings,
            dataset_id,
            ["Use in Newsletter", "SNS Only"],
        ),
        max_items=3,
    )

    newsletter_warnings: list[str] = []
    social_warnings: list[str] = []
    llm_client = None
    if newsletter_articles or social_articles:
        llm_client = LlmClient(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            prompt_directory=settings.prompt_directory,
            company_topics=settings.discovery_topics,
        )

    refresh_records: list[EvidenceRefreshRecord] = []
    if refresh_evidence and llm_client is not None:
        refresh_records = _refresh_preview_evidence(
            newsletter_articles,
            social_articles,
            llm_client,
            ArticleRetriever(),
            publisher_url_overrides or {},
        )

    if newsletter_articles and llm_client is not None:
        newsletter_draft = llm_client.generate_newsletter_draft(
            week.start.isoformat(),
            week.end.isoformat(),
            format_newsletter_articles_for_prompt(newsletter_articles),
        )
        newsletter_warnings = validate_newsletter_draft(
            newsletter_draft,
            newsletter_articles,
        )
        newsletter_path = preview_dir / (
            "newsletter_evidence_preview.md"
            if refresh_evidence
            else "newsletter_preview.md"
        )
        newsletter_path.write_text(newsletter_draft, encoding="utf-8")
        created_paths.append(newsletter_path)
        print_validation_warnings("Newsletter preview", newsletter_warnings, output=output)

    if social_articles and llm_client is not None:
        social_draft = llm_client.generate_social_media_draft(
            week.start.isoformat(),
            week.end.isoformat(),
            format_social_articles_for_prompt(social_articles),
        )
        social_warnings = validate_social_draft(social_draft, social_articles)
        social_path = preview_dir / (
            "sns_evidence_preview.md" if refresh_evidence else "sns_preview.md"
        )
        social_path.write_text(social_draft, encoding="utf-8")
        created_paths.append(social_path)
        print_validation_warnings("SNS preview", social_warnings, output=output)

    if refresh_evidence:
        summary = _evidence_report(
            week.start.isoformat(),
            week.end.isoformat(),
            refresh_records,
            newsletter_warnings,
            social_warnings,
        )
    else:
        summary = _preview_summary(
            week.start.isoformat(),
            week.end.isoformat(),
            newsletter_articles,
            social_articles,
            newsletter_warnings,
            social_warnings,
        )
    summary_path.write_text(summary, encoding="utf-8")
    created_paths.append(summary_path)

    if refresh_evidence:
        refreshed_count = sum(record.full_article_enriched for record in refresh_records)
        output(
            "Evidence refresh completed in memory: "
            f"{refreshed_count}/{len(refresh_records)} selected stories used full article text."
        )
    output("Preview mode: no Notion writes, status changes, relation updates, or images.")
    for path in created_paths:
        output(f"Preview file: {path.resolve()}")
    return created_paths


def _refresh_preview_evidence(
    newsletter_articles: list[DraftArticle],
    social_articles: list[DraftArticle],
    llm_client: LlmClient,
    retriever: ArticleRetriever,
    publisher_url_overrides: dict[str, str],
) -> list[EvidenceRefreshRecord]:
    """Retrieve and enrich each selected story once, entirely in memory."""

    refreshed: dict[tuple[str, str], tuple[DraftArticle, EvidenceRefreshRecord]] = {}
    records: list[EvidenceRefreshRecord] = []
    for draft_article in [*newsletter_articles, *social_articles]:
        key = (
            draft_article.title.casefold(),
            clean_url(draft_article.canonical_url),
        )
        cached = refreshed.get(key)
        if cached is not None:
            _copy_refreshed_evidence(cached[0], draft_article)
            continue

        original_url = clean_url(draft_article.canonical_url)
        retrieval_url = _publisher_url_override(
            draft_article.title,
            publisher_url_overrides,
        ) or original_url
        article = Article(
            title=draft_article.title,
            url=original_url,
            canonical_url=retrieval_url,
            source_name=draft_article.source_name,
            source_page_id="",
            snippet=draft_article.summary,
            region=list(draft_article.region),
            topic_focus=list(draft_article.topic),
        )

        try:
            retrieval = retriever.retrieve(article)
        except Exception:
            retrieval = ArticleRetrievalResult(
                canonical_url=retrieval_url,
                url_resolution_status=(
                    "unresolved" if is_google_news_url(retrieval_url) else "publisher_url"
                ),
                evidence_retrieval_status="fetch_failed",
            )
        apply_retrieval_result(article, retrieval)

        enrichment_error = ""
        try:
            enrichment = llm_client.enrich_article(article)
        except Exception as exc:
            enrichment = None
            enrichment_error = f"{type(exc).__name__}: {exc}"

        draft_article.evidence_retrieval_status = retrieval.evidence_retrieval_status
        if article.canonical_url and not is_google_news_url(article.canonical_url):
            draft_article.resolved_publisher_url = article.canonical_url
        if enrichment is not None:
            draft_article.summary = enrichment.summary or draft_article.summary
            draft_article.why_it_matters = (
                enrichment.why_it_matters or draft_article.why_it_matters
            )
            draft_article.newsletter_angle = (
                enrichment.newsletter_angle or draft_article.newsletter_angle
            )
            draft_article.sns_hook = enrichment.sns_hook or draft_article.sns_hook
            draft_article.topic = enrichment.topic or draft_article.topic
            draft_article.region = enrichment.region or draft_article.region
            draft_article.factual_points = list(enrichment.factual_points)

        limitation = _source_limitation(
            retrieval.evidence_retrieval_status,
            draft_article.factual_points,
            enrichment_error,
        )
        record = EvidenceRefreshRecord(
            title=draft_article.title,
            original_url=original_url,
            retrieval_url=retrieval_url,
            resolved_url=draft_article.resolved_publisher_url,
            url_resolution_status=retrieval.url_resolution_status,
            evidence_retrieval_status=retrieval.evidence_retrieval_status,
            factual_points=tuple(draft_article.factual_points),
            source_limitation=limitation,
            enrichment_error=enrichment_error,
        )
        refreshed[key] = (draft_article, record)
        records.append(record)
    return records


def _copy_refreshed_evidence(source: DraftArticle, target: DraftArticle) -> None:
    target.summary = source.summary
    target.why_it_matters = source.why_it_matters
    target.newsletter_angle = source.newsletter_angle
    target.sns_hook = source.sns_hook
    target.topic = list(source.topic)
    target.region = list(source.region)
    target.factual_points = list(source.factual_points)
    target.evidence_retrieval_status = source.evidence_retrieval_status
    target.resolved_publisher_url = source.resolved_publisher_url


def _source_limitation(
    retrieval_status: str,
    factual_points: list[str],
    enrichment_error: str,
) -> str:
    if enrichment_error:
        return "Article retrieval may have succeeded, but LLM enrichment failed."
    if retrieval_status.casefold() == "extracted":
        if factual_points:
            return "No retrieval limitation identified; facts came from extracted article text."
        return "Article text was extracted, but enrichment returned no factual points."
    if retrieval_status.casefold() == "blocked":
        return "Publisher blocked retrieval; enrichment used legacy summary context only."
    if retrieval_status.casefold() == "insufficient_content":
        return "Publisher page lacked sufficient extractable text; legacy summary fallback used."
    return (
        f"Full article text was unavailable ({retrieval_status or 'unknown status'}); "
        "enrichment used legacy summary context only."
    )


def _parse_publisher_url_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        title_match, separator, raw_url = value.partition("=")
        title_match = title_match.strip().casefold()
        url = clean_url(raw_url.strip())
        if not separator or not title_match or not url_hostname(url):
            raise ValueError(
                "Publisher URL overrides must use TITLE_MATCH=https://publisher.example/story"
            )
        overrides[title_match] = url
    return overrides


def _publisher_url_override(title: str, overrides: dict[str, str]) -> str:
    matches = [
        (title_match, url)
        for title_match, url in overrides.items()
        if title_match in title.casefold()
    ]
    if not matches:
        return ""
    return max(matches, key=lambda item: len(item[0]))[1]


def _evidence_report(
    week_start: str,
    week_end: str,
    records: list[EvidenceRefreshRecord],
    newsletter_warnings: list[str],
    social_warnings: list[str],
) -> str:
    full_count = sum(record.full_article_enriched for record in records)
    lines = [
        "# Evidence Refresh Preview Report",
        "",
        f"Week: {week_start} to {week_end}",
        "",
        "This evaluation was read-only for Notion and local ingestion state.",
        "Image selection and image-cache behavior were not evaluated.",
        f"Full-article enrichment succeeded for {full_count}/{len(records)} selected stories.",
    ]
    for record in records:
        warnings = _article_warnings(
            record.title,
            newsletter_warnings,
            social_warnings,
        )
        lines.extend(
            [
                "",
                f"## {record.title}",
                f"- Original URL: {record.original_url or 'Not available'}",
                *(
                    [f"- Retrieval input URL: {record.retrieval_url}"]
                    if record.retrieval_url != record.original_url
                    else []
                ),
                f"- Resolved URL: {record.resolved_url or 'Not available'}",
                f"- URL resolution status: {record.url_resolution_status or 'unknown'}",
                f"- Evidence retrieval status: {record.evidence_retrieval_status or 'unknown'}",
                f"- Full-article evidence used: {'Yes' if record.full_article_enriched else 'No'}",
                f"- Factual points extracted: {len(record.factual_points)}",
                f"- Source limitations: {record.source_limitation}",
            ]
        )
        if record.enrichment_error:
            lines.append(f"- Enrichment error: {record.enrichment_error}")
        lines.append("- Important facts and figures:")
        lines.extend(
            [f"  - {point}" for point in record.factual_points]
            or ["  - None extracted."]
        )
        lines.append("- Validation warnings:")
        lines.extend([f"  - {warning}" for warning in warnings] or ["  - None."])

    lines.extend(
        [
            "",
            "## Newsletter validation warnings",
            *_warning_lines(newsletter_warnings),
            "",
            "## SNS validation warnings",
            *_warning_lines(social_warnings),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _article_warnings(
    title: str,
    newsletter_warnings: list[str],
    social_warnings: list[str],
) -> list[str]:
    title_key = title.casefold()
    return [
        warning
        for warning in [*newsletter_warnings, *social_warnings]
        if title_key in warning.casefold()
    ]


def _preview_summary(
    week_start: str,
    week_end: str,
    newsletter_articles,
    social_articles,
    newsletter_warnings: list[str],
    social_warnings: list[str],
) -> str:
    lines = [
        "# Weekly Draft Preview",
        "",
        f"Week: {week_start} to {week_end}",
        "",
        "Preview is read-only for Notion and local ingestion state.",
        "Image selection and image-cache behavior were not evaluated.",
        "",
    ]
    lines.extend(_article_summary_section("Newsletter articles", newsletter_articles))
    lines.append("")
    lines.extend(_article_summary_section("SNS articles", social_articles))
    lines.extend(
        [
            "",
            "## Newsletter validation warnings",
            *(_warning_lines(newsletter_warnings)),
            "",
            "## SNS validation warnings",
            *(_warning_lines(social_warnings)),
        ]
    )

    selected = [*newsletter_articles, *social_articles]
    if selected and not any(_has_research_notes(article) for article in selected):
        lines.extend(
            [
                "",
                "## Important limitation",
                "All selected articles lack Research Notes. This preview evaluates only "
                "the legacy summary fallback, not evidence-grounded generation.",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _article_summary_section(title: str, articles) -> list[str]:
    lines = [f"## {title}"]
    if not articles:
        return [*lines, "- None selected."]
    for article in articles:
        status = article.evidence_retrieval_status or "Not available (legacy entry)"
        publisher_url = article.resolved_publisher_url or article.canonical_url
        publisher_available = bool(publisher_url and not is_google_news_url(publisher_url))
        lines.extend(
            [
                f"- {article.title}",
                f"  - Research Notes: {'Yes' if _has_research_notes(article) else 'No'}",
                f"  - Evidence status: {status}",
                f"  - Original publisher URL: {'Yes' if publisher_available else 'No'}",
            ]
        )
    return lines


def _has_research_notes(article) -> bool:
    return bool(
        article.factual_points
        or article.evidence_retrieval_status
        or article.resolved_publisher_url
    )


def _warning_lines(warnings: list[str]) -> list[str]:
    return [f"- {warning}" for warning in warnings] or ["- None."]


if __name__ == "__main__":
    main()

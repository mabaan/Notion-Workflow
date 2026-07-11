"""Generate weekly Newsletter and Social Media drafts from approved articles."""

from __future__ import annotations

from research_automation.clients.llm_client import LlmClient
from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings
from research_automation.logging_config import configure_logging
from research_automation.pipeline.draft import (
    format_articles_for_prompt,
    load_weekly_draft_articles,
    select_featured_articles,
)
from research_automation.pipeline.images import (
    ArticleImageResolver,
    inject_story_images,
)
from research_automation.pipeline.notion_write import (
    mark_newsletter_ready_for_review,
    mark_social_media_ready,
    replace_generated_section,
)
from research_automation.pipeline.weekly_pages import ensure_current_weekly_pages


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    notion = NotionClient(token=settings.notion_token)

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
            format_articles_for_prompt(newsletter_articles),
        )
        newsletter_draft = inject_story_images(newsletter_draft, newsletter_articles)
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
            format_articles_for_prompt(social_articles),
        )
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


if __name__ == "__main__":
    main()

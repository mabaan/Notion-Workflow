"""Create or find the current week's linked Notion pages."""

from __future__ import annotations

from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings
from research_automation.logging_config import configure_logging
from research_automation.pipeline.weekly_pages import ensure_current_weekly_pages


def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    notion = NotionClient(token=settings.notion_token)
    weekly_pages = ensure_current_weekly_pages(notion, settings)

    print(f"Week start: {weekly_pages.week.start.isoformat()}")
    print(f"Week end: {weekly_pages.week.end.isoformat()}")
    print(f"Dataset Meeting page: {weekly_pages.dataset_meeting_id}")
    print(f"Newsletter page: {weekly_pages.newsletter_id}")
    print(f"Social Media page: {weekly_pages.social_media_id}")
    print("Weekly setup completed.")


if __name__ == "__main__":
    main()

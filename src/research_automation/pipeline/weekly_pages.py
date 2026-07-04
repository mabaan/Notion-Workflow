"""Find or create the current week's Notion pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from research_automation.clients.notion_client import NotionClient
from research_automation.config import Settings
from research_automation.notion_schema import (
    DATASET_MEETINGS,
    NEWSLETTERS,
    SOCIAL_MEDIA,
    DATASET_STATUS_NOT_STARTED,
    NEWSLETTER_STATUS_NOT_STARTED,
    SOCIAL_REVIEWED_NOT_YET,
    SOCIAL_STATUS_NOT_READY,
)
from research_automation.pipeline.notion_write import ensure_relation_contains
from research_automation.utils import notion_properties as props
from research_automation.utils.dates import (
    WorkWeek,
    current_workweek,
    format_dataset_meeting_title,
    format_social_media_title,
)
from research_automation.utils.edition_numbers import next_newsletter_edition


@dataclass
class WeeklyPages:
    """The current week's linked Notion pages."""

    week: WorkWeek
    dataset_meeting_page: dict[str, Any]
    newsletter_page: dict[str, Any]
    social_media_page: dict[str, Any]

    @property
    def dataset_meeting_id(self) -> str:
        return self.dataset_meeting_page["id"]

    @property
    def newsletter_id(self) -> str:
        return self.newsletter_page["id"]

    @property
    def social_media_id(self) -> str:
        return self.social_media_page["id"]


def ensure_current_weekly_pages(
    notion: NotionClient,
    settings: Settings,
    reference_date: date | None = None,
) -> WeeklyPages:
    """Find or create the current Dataset Meeting, Newsletter, and Social pages."""

    week = current_workweek(reference_date)

    dataset_page = find_dataset_meeting_for_week(notion, settings, week)
    if dataset_page is None:
        dataset_page = notion.create_page(
            settings.notion_dataset_meetings_database_id,
            {
                DATASET_MEETINGS["title"]: props.title(
                    format_dataset_meeting_title(week.start, week.end)
                ),
                DATASET_MEETINGS["date_presented"]: props.date_value(week.end),
                DATASET_MEETINGS["year"]: props.rich_text(str(week.start.year)),
                DATASET_MEETINGS["week_start"]: props.date_value(week.start),
                DATASET_MEETINGS["week_end"]: props.date_value(week.end),
                DATASET_MEETINGS["status"]: props.status(DATASET_STATUS_NOT_STARTED),
            },
        )

    newsletter_page = find_newsletter_for_week(notion, settings, week)
    if newsletter_page is None:
        newsletter_page = notion.create_page(
            settings.notion_newsletters_database_id,
            {
                **_newsletter_identity_properties(notion, settings),
                NEWSLETTERS["status"]: props.status(NEWSLETTER_STATUS_NOT_STARTED),
                NEWSLETTERS["publish_date"]: props.date_value(week.end),
                NEWSLETTERS["dataset_source"]: props.relation([dataset_page["id"]]),
            },
        )

    social_media_page = find_social_media_for_week(notion, settings, week)
    if social_media_page is None:
        social_media_page = notion.create_page(
            settings.notion_social_media_database_id,
            {
                SOCIAL_MEDIA["title"]: props.title(format_social_media_title(week.start)),
                SOCIAL_MEDIA["content_status"]: props.status(SOCIAL_STATUS_NOT_READY),
                SOCIAL_MEDIA["reviewed"]: props.status(SOCIAL_REVIEWED_NOT_YET),
                SOCIAL_MEDIA["newsletter_source"]: props.relation([newsletter_page["id"]]),
                SOCIAL_MEDIA["week_start"]: props.date_value(week.start),
                SOCIAL_MEDIA["week_end"]: props.date_value(week.end),
                SOCIAL_MEDIA["dataset_source"]: props.relation([dataset_page["id"]]),
            },
        )

    weekly_pages = WeeklyPages(
        week=week,
        dataset_meeting_page=dataset_page,
        newsletter_page=newsletter_page,
        social_media_page=social_media_page,
    )
    _ensure_links(notion, weekly_pages)
    return weekly_pages


def find_dataset_meeting_for_week(
    notion: NotionClient,
    settings: Settings,
    week: WorkWeek,
) -> dict[str, Any] | None:
    """Find the Dataset Meeting for a week by date range."""

    rows = notion.query_database(
        settings.notion_dataset_meetings_database_id,
        filter_payload={
            "and": [
                {
                    "property": DATASET_MEETINGS["week_start"],
                    "date": {"equals": week.start.isoformat()},
                },
                {
                    "property": DATASET_MEETINGS["week_end"],
                    "date": {"equals": week.end.isoformat()},
                },
            ]
        },
        max_results=1,
    )
    return rows[0] if rows else None


def find_newsletter_for_week(
    notion: NotionClient,
    settings: Settings,
    week: WorkWeek,
) -> dict[str, Any] | None:
    """Find the Newsletter page for a week by publish date."""

    rows = notion.query_database(
        settings.notion_newsletters_database_id,
        filter_payload={
            "property": NEWSLETTERS["publish_date"],
            "date": {"equals": week.end.isoformat()},
        },
        max_results=1,
    )
    return rows[0] if rows else None


def find_social_media_for_week(
    notion: NotionClient,
    settings: Settings,
    week: WorkWeek,
) -> dict[str, Any] | None:
    """Find the Social Media page for a week by date range."""

    rows = notion.query_database(
        settings.notion_social_media_database_id,
        filter_payload={
            "and": [
                {
                    "property": SOCIAL_MEDIA["week_start"],
                    "date": {"equals": week.start.isoformat()},
                },
                {
                    "property": SOCIAL_MEDIA["week_end"],
                    "date": {"equals": week.end.isoformat()},
                },
            ]
        },
        max_results=1,
    )
    return rows[0] if rows else None


def _newsletter_identity_properties(
    notion: NotionClient,
    settings: Settings,
) -> dict[str, Any]:
    rows = notion.query_database(settings.notion_newsletters_database_id)
    code_values = [
        _rich_text_text(page.get("properties", {}).get(NEWSLETTERS["code"], {}))
        for page in rows
    ]
    edition = next_newsletter_edition(code_values)
    return {
        NEWSLETTERS["code"]: props.rich_text(edition.code),
        NEWSLETTERS["title"]: props.title(edition.title),
    }


def _ensure_links(notion: NotionClient, weekly_pages: WeeklyPages) -> None:
    ensure_relation_contains(
        notion,
        weekly_pages.dataset_meeting_page,
        DATASET_MEETINGS["newsletter"],
        [weekly_pages.newsletter_id],
    )
    ensure_relation_contains(
        notion,
        weekly_pages.newsletter_page,
        NEWSLETTERS["dataset_source"],
        [weekly_pages.dataset_meeting_id],
    )
    ensure_relation_contains(
        notion,
        weekly_pages.newsletter_page,
        NEWSLETTERS["social_media_script"],
        [weekly_pages.social_media_id],
    )
    ensure_relation_contains(
        notion,
        weekly_pages.social_media_page,
        SOCIAL_MEDIA["newsletter_source"],
        [weekly_pages.newsletter_id],
    )
    ensure_relation_contains(
        notion,
        weekly_pages.social_media_page,
        SOCIAL_MEDIA["dataset_source"],
        [weekly_pages.dataset_meeting_id],
    )


def _rich_text_text(property_value: dict[str, Any]) -> str:
    return "".join(
        item.get("plain_text", "") for item in property_value.get("rich_text", [])
    ).strip()

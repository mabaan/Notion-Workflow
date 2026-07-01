"""Test Notion connection by reading Source Registry rows."""

from __future__ import annotations

from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings


def get_title(properties: dict) -> str:
    """Extract Source Name title from a Notion page."""

    title_property = properties.get("Source Name", {})
    title_items = title_property.get("title", [])

    if not title_items:
        return "Untitled"

    return title_items[0].get("plain_text", "Untitled")


def main() -> None:
    """Run the Notion connection test."""

    settings = load_settings()

    notion = NotionClient(token=settings.notion_token)

    rows = notion.query_database(
        database_id=settings.notion_source_registry_database_id,
        page_size=10,
    )

    print(f"Connected to Notion. Found {len(rows)} source rows.")

    for row in rows:
        print("-", get_title(row.get("properties", {})))


if __name__ == "__main__":
    main()
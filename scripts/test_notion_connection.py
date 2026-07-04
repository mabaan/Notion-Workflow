"""Test Notion connection by reading Source Registry rows."""

from __future__ import annotations

from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings
from research_automation.notion_schema import SOURCE_REGISTRY


def get_title(properties: dict) -> str:
    """Extract Source Name title from a Notion page."""

    title_property = properties.get(SOURCE_REGISTRY["title"], {})
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
        page_size=5,
        max_results=5,
    )

    print("Connected to Notion successfully.")
    print(f"Read {len(rows)} Source Registry rows.")

    for row in rows:
        print("-", get_title(row.get("properties", {})))

    print("Source Registry connection test passed.")


if __name__ == "__main__":
    main()

"""Inspect a configured Notion database schema."""

from __future__ import annotations

import argparse

from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings
from research_automation.notion_schema import DATABASE_ID_FIELDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", choices=sorted(DATABASE_ID_FIELDS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    notion = NotionClient(token=settings.notion_token)

    database_id = settings.database_id(args.database)
    database = notion.retrieve_database(database_id)
    properties = database.get("properties", {})

    print(f"Database: {args.database}")
    for name, metadata in properties.items():
        print(f"- {name}: {metadata.get('type')}")


if __name__ == "__main__":
    main()

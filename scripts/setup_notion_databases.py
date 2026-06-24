"""Create or validate the Notion database setup."""

from __future__ import annotations

from research_automation.config import load_settings


def main() -> None:
    """Run the Notion database setup helper."""

    settings = load_settings()
    if not settings.notion_token:
        print("NOTION_TOKEN is not configured.")
        return
    print("Notion setup placeholder: add database creation logic here.")


if __name__ == "__main__":
    main()


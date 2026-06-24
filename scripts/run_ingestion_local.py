"""Run article ingestion locally."""

from __future__ import annotations

from research_automation.handlers.ingest_articles import handler


def main() -> None:
    """Run local ingestion."""

    result = handler({}, None)
    print(result)


if __name__ == "__main__":
    main()


"""Run weekly draft generation locally."""

from __future__ import annotations

from research_automation.handlers.generate_weekly_drafts import handler


def main() -> None:
    """Run local weekly draft generation."""

    result = handler({}, None)
    print(result)


if __name__ == "__main__":
    main()


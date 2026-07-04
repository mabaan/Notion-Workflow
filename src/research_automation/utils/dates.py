"""Date utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from research_automation.utils.edition_numbers import ordinal


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(UTC)


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string."""

    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


@dataclass(frozen=True)
class WorkWeek:
    """Simple Monday-to-Friday work week window."""

    start: date
    end: date


def current_workweek(reference_date: date | None = None) -> WorkWeek:
    """Return the current Monday-to-Friday work week."""

    today = reference_date or datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return WorkWeek(start=monday, end=friday)


def format_dataset_meeting_title(start: date, end: date) -> str:
    """Format the Dataset Meeting page title."""

    return f"{start.strftime('%B')} {ordinal(start.day)} to {end.strftime('%B')} {ordinal(end.day)}"


def format_social_media_title(start: date) -> str:
    """Format the Social Media page title."""

    return f"Content for week {start.strftime('%d.%m.%Y')}"

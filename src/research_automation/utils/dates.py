"""Date utilities."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC datetime."""

    return datetime.now(UTC)


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string."""

    return datetime.fromisoformat(value)


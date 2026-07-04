"""Helpers for building Notion property payloads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from research_automation.utils.text import normalize_whitespace

RICH_TEXT_LIMIT = 1900


def _chunk_text(text: str, limit: int = RICH_TEXT_LIMIT) -> list[str]:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []

    chunks: list[str] = []
    remaining = cleaned
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        slice_text = remaining[:limit]
        split_at = slice_text.rfind(" ")
        if split_at <= limit // 2:
            split_at = limit
        chunk = remaining[:split_at].rstrip()
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    return chunks


def rich_text_items(value: str) -> list[dict[str, Any]]:
    """Build Notion rich text items with truncation-safe chunking."""

    return [
        {
            "type": "text",
            "text": {"content": chunk},
        }
        for chunk in _chunk_text(value)
    ]


def title(value: str) -> dict[str, Any]:
    """Build a title property."""

    content = value.strip() or "Untitled"
    return {"title": rich_text_items(content)}


def rich_text(value: str) -> dict[str, Any]:
    """Build a rich text property."""

    return {"rich_text": rich_text_items(value)}


def url(value: str | None) -> dict[str, Any]:
    """Build a URL property."""

    return {"url": value or None}


def date_value(value: date | datetime | str | None) -> dict[str, Any]:
    """Build a date property."""

    if value is None:
        return {"date": None}

    if isinstance(value, str):
        start = value
    elif isinstance(value, datetime):
        start = value.isoformat()
    else:
        start = value.isoformat()
    return {"date": {"start": start}}


def checkbox(value: bool) -> dict[str, Any]:
    """Build a checkbox property."""

    return {"checkbox": value}


def number(value: int | float | None) -> dict[str, Any]:
    """Build a number property."""

    return {"number": value}


def select(value: str | None) -> dict[str, Any]:
    """Build a select property."""

    return {"select": {"name": value} if value else None}


def status(value: str | None) -> dict[str, Any]:
    """Build a status property."""

    return {"status": {"name": value} if value else None}


def multi_select(values: list[str]) -> dict[str, Any]:
    """Build a multi-select property."""

    seen: set[str] = set()
    options: list[dict[str, str]] = []
    for value in values:
        name = normalize_whitespace(value)
        if not name or name in seen:
            continue
        seen.add(name)
        options.append({"name": name})
    return {"multi_select": options}


def relation(page_ids: list[str]) -> dict[str, Any]:
    """Build a relation property."""

    seen: set[str] = set()
    items: list[dict[str, str]] = []
    for page_id in page_ids:
        if not page_id or page_id in seen:
            continue
        seen.add(page_id)
        items.append({"id": page_id})
    return {"relation": items}

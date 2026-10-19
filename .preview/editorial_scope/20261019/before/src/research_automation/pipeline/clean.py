"""Article cleaning helpers."""

from __future__ import annotations

from research_automation.utils.text import normalize_whitespace, strip_html


def clean_text(text: str) -> str:
    """Normalize text captured from a feed or prompt context."""

    return normalize_whitespace(strip_html(text))


def clean_snippet(text: str, max_length: int = 600) -> str:
    """Normalize and lightly cap feed snippet text."""

    cleaned = clean_text(text)
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[:max_length].rstrip()}..."

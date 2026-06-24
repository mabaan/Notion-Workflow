"""Text utilities."""

from __future__ import annotations


def truncate(text: str, max_length: int) -> str:
    """Truncate text to a maximum length."""

    if max_length < 0:
        raise ValueError("max_length must be non-negative")
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip()


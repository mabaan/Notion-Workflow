"""Article cleaning helpers."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace and trim surrounding space."""

    return _WHITESPACE_RE.sub(" ", text).strip()


def clean_text(text: str) -> str:
    """Normalize text captured from an article."""

    return normalize_whitespace(text)


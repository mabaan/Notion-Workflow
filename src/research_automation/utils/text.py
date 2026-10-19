"""Text utilities."""

from __future__ import annotations

import html
import re

_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace and trim surrounding space."""

    return _WHITESPACE_RE.sub(" ", text).strip()


def strip_html(text: str) -> str:
    """Remove basic HTML tags and decode entities."""

    return normalize_whitespace(html.unescape(_HTML_TAG_RE.sub(" ", text)))

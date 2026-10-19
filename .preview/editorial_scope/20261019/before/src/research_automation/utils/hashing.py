"""Hashing utilities."""

from __future__ import annotations

import hashlib

from research_automation.utils.text import normalize_whitespace


def stable_hash(value: str) -> str:
    """Return a deterministic SHA-256 hash for a string."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_url_hash(canonical_url: str) -> str:
    """Create the stable URL hash used for local deduplication."""

    return stable_hash(canonical_url.strip())


def build_content_hash(title: str, source_name: str) -> str:
    """Create a stable content hash from normalized title and source name."""

    normalized_title = normalize_whitespace(title).casefold()
    normalized_source = normalize_whitespace(source_name).casefold()
    return stable_hash(f"{normalized_title}|{normalized_source}")

"""Draft models used for newsletter and social generation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DraftArticle:
    """Article context used when generating weekly drafts."""

    title: str
    source_name: str
    canonical_url: str
    summary: str = ""
    why_it_matters: str = ""
    newsletter_angle: str = ""
    sns_hook: str = ""
    topic: list[str] = field(default_factory=list)
    region: list[str] = field(default_factory=list)
    relevance_score: int = 0
    image_url: str = ""


@dataclass
class GeneratedDraft:
    """Generated draft content."""

    title: str
    content: str

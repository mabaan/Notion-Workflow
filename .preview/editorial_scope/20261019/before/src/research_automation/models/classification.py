"""Metadata-only classifier contracts; independent of Notion and enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


REGIONS = ("Global", "UAE", "KSA", "Egypt", "Out of Scope/Unclear")
TOPICS = ("Food Security", "Water Security", "Net Zero Transition", "Other/Unclear")
DECISIONS = ("Relevant", "Borderline", "Irrelevant")


@dataclass(frozen=True)
class ClassificationInput:
    article_id: str
    title: str
    snippet: str
    publisher: str
    published_date: datetime | None
    source_region_hints: tuple[str, ...] = ()

    def as_record(self) -> dict:
        """Deliberately exclude URLs, full article bodies and source quality."""

        return {
            "article_id": self.article_id,
            "title": self.title,
            "snippet": self.snippet,
            "publisher": self.publisher,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "source_region_hints_not_evidence": list(self.source_region_hints),
        }


@dataclass(frozen=True)
class ArticleClassification:
    article_id: str
    relevance_score: int
    assigned_region: str
    primary_mission_topic: str
    decision: str
    justification: str


@dataclass(frozen=True)
class ClassificationOutcome:
    article_id: str
    classification: ArticleClassification | None = None
    error: str | None = None

    @property
    def eligible_for_assessment(self) -> bool:
        """An operational failure must never become an editorial rejection."""

        return self.classification is None or self.classification.decision != "Irrelevant"


@dataclass
class ClassificationRequest:
    article_ids: tuple[str, ...]
    requested_model: str
    attempt: int
    status: str = "pending"
    returned_model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class ClassificationReport:
    model: str
    outcomes: list[ClassificationOutcome] = field(default_factory=list)
    requests: list[ClassificationRequest] = field(default_factory=list)
    split_count: int = 0

    @property
    def request_count(self) -> int:
        return len(self.requests)

    @property
    def failed_ids(self) -> list[str]:
        return [outcome.article_id for outcome in self.outcomes if outcome.error]

    @property
    def eligible_ids(self) -> list[str]:
        return [outcome.article_id for outcome in self.outcomes if outcome.eligible_for_assessment]

    @property
    def token_usage(self) -> dict[str, int]:
        """Reported usage only; failures without usage are explicitly counted."""

        return {
            key: sum(getattr(request, key) or 0 for request in self.requests)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }

    @property
    def requests_without_usage(self) -> int:
        return sum(request.total_tokens is None for request in self.requests)

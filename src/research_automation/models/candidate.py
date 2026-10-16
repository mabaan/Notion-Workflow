"""Internal candidate evaluation models used before any Notion write."""

from __future__ import annotations

from dataclasses import dataclass, field

from research_automation.models.article import Article, EnrichedArticle


@dataclass
class CandidateResult:
    """A candidate's complete gate, enrichment, and ranking state."""

    article: Article
    enrichment: EnrichedArticle | None
    target_region: str | None
    queue_score: float = 0.0
    source_quality: float | None = None
    rejection_reason: str = ""
    matched_topics: list[str] = field(default_factory=list)
    direct_mission_signals: list[str] = field(default_factory=list)
    selection_reason: str = ""
    candidate_id: str = ""
    region_assignment_basis: str = ""
    contextual_signals: list[str] = field(default_factory=list)
    mission_specificity: int = 0
    concrete_development: bool = False
    metadata_rank: int | None = None
    allocation_rank: int | None = None
    phase: str = "rss"
    shortlisted: bool = False
    enrichment_attempted: bool = False
    source_region_hints: list[str] = field(default_factory=list)
    required_relevance_score: int | None = None

    @property
    def eligible(self) -> bool:
        return not self.rejection_reason and self.enrichment is not None


@dataclass
class CandidateEvaluation:
    """Pool evaluation output and counts for run reporting."""

    results: list[CandidateResult] = field(default_factory=list)
    rejection_counts: dict[str, int] = field(default_factory=dict)
    shortlisted_counts: dict[str, int] = field(default_factory=dict)
    enriched_counts: dict[str, int] = field(default_factory=dict)

    def reject(self, result: CandidateResult, reason: str) -> None:
        result.rejection_reason = reason
        self.results.append(result)
        self.rejection_counts[reason] = self.rejection_counts.get(reason, 0) + 1

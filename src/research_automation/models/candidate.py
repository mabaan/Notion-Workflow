"""Internal candidate evaluation models used before any Notion write."""

from __future__ import annotations

from dataclasses import dataclass, field

from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.classification import ArticleClassification, ClassificationReport
from research_automation.models.editorial import editorial_rejection_reason
from research_automation.utils.regions import TARGET_REGION_ORDER


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
    objective_cleanup_reason: str = ""
    classification_attempted: bool = False
    classification: ArticleClassification | None = None
    classification_error: str | None = None
    selection_rejection_reason: str = ""
    regional_overflow: bool = False
    selection_tier: str | None = None
    fallback_reason: str = ""
    publication_failure_reason: str = ""

    @property
    def editorial_rejection_reason(self) -> str:
        if self.enrichment is None:
            return ""
        return editorial_rejection_reason(
            getattr(self.enrichment, "story_type", "other"),
            getattr(self.enrichment, "is_new_development", "unclear"),
        )

    @property
    def eligible(self) -> bool:
        return (
            not self.rejection_reason and self.enrichment is not None
            and not self.editorial_rejection_reason
        )

    @property
    def fallback_eligible(self) -> bool:
        """Relax only the final relevance gate, never another rejection.

        Missing full text alone is not a factual failure. An explicit publication
        failure must be recorded separately; fallback cannot override it.
        """

        required = self.required_relevance_score or 4
        return (
            self.enrichment is not None
            and self.enrichment.relevance_score >= 3
            and self.enrichment.relevance_score < max(4, required)
            and self.enrichment.editorial_significance >= 3
            and bool(self.article.source_page_id)
            and self.target_region in TARGET_REGION_ORDER
            and not self.objective_cleanup_reason
            and not self.publication_failure_reason
            and not self.editorial_rejection_reason
            and self.article.evidence_retrieval_status != "invalid_url"
            and self.rejection_reason in {"", f"relevance below {required}"}
        )


@dataclass
class CandidateEvaluation:
    """Pool evaluation output and counts for run reporting."""

    results: list[CandidateResult] = field(default_factory=list)
    rejection_counts: dict[str, int] = field(default_factory=dict)
    shortlisted_counts: dict[str, int] = field(default_factory=dict)
    enriched_counts: dict[str, int] = field(default_factory=dict)
    classification_reports: list[ClassificationReport] = field(default_factory=list)

    def reject(self, result: CandidateResult, reason: str) -> None:
        result.rejection_reason = reason
        self.results.append(result)
        self.rejection_counts[reason] = self.rejection_counts.get(reason, 0) + 1

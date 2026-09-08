"""Weekly state loading, event suppression, and constrained final selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
import re
from typing import Any

from research_automation.config import Settings
from research_automation.models.candidate import CandidateResult
from research_automation.notion_schema import ARTICLE_QUEUE
from research_automation.utils.regions import (
    TARGET_REGION_ORDER,
    add_primary_region_count,
    target_deficits,
)
from research_automation.utils.urls import clean_url, url_hostname

EVENT_TITLE_SIMILARITY_THRESHOLD = 0.72
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PUBLISHER_SUFFIX_RE = re.compile(r"\s+(?:[-|:])\s+[^-|:]{2,50}$")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "in", "into", "is", "it", "its", "new", "of", "on", "says", "the", "to",
    "with", "will", "energy", "transition", "investment", "investments", "expands",
}


@dataclass
class WeeklyQueueState:
    """Current week's hard constraints and event-dedupe context."""

    region_counts: dict[str, int] = field(
        default_factory=lambda: {region: 0 for region in TARGET_REGION_ORDER}
    )
    publisher_counts: dict[str, int] = field(default_factory=dict)
    existing_urls: set[str] = field(default_factory=set)
    existing_titles: list[str] = field(default_factory=list)


@dataclass
class SelectionResult:
    winners: list[CandidateResult]
    final_state: WeeklyQueueState
    shortages: dict[str, int]
    rejected_by_constraint: dict[str, int]


def load_weekly_queue_state(
    notion,
    settings: Settings,
    dataset_meeting_page_id: str | None,
) -> WeeklyQueueState:
    """Load region, publisher, URL, and title state for one Dataset Meeting."""

    state = WeeklyQueueState()
    if not dataset_meeting_page_id:
        return state
    pages = notion.query_database(
        settings.notion_article_queue_database_id,
        filter_payload={
            "property": ARTICLE_QUEUE["dataset_meeting"],
            "relation": {"contains": dataset_meeting_page_id},
        },
    )
    for page in pages:
        properties = page.get("properties", {})
        regions = [
            option.get("name", "")
            for option in properties.get(ARTICLE_QUEUE["region"], {}).get(
                "multi_select", []
            )
            if option.get("name")
        ]
        add_primary_region_count(state.region_counts, regions)
        canonical_url = clean_url(
            properties.get(ARTICLE_QUEUE["canonical_url"], {}).get("url")
            or properties.get(ARTICLE_QUEUE["url"], {}).get("url")
            or ""
        )
        if canonical_url:
            state.existing_urls.add(canonical_url)
        title = _title_text(properties.get(ARTICLE_QUEUE["title"], {}))
        if title:
            state.existing_titles.append(title)
        relations = properties.get(ARTICLE_QUEUE["source"], {}).get("relation", [])
        publisher_key = str(relations[0].get("id") or "") if relations else ""
        publisher_key = publisher_key or url_hostname(canonical_url)
        if publisher_key:
            state.publisher_counts[publisher_key] = (
                state.publisher_counts.get(publisher_key, 0) + 1
            )
    state.existing_titles.sort(key=str.casefold)
    return state


def select_final_candidates(
    candidates: list[CandidateResult],
    *,
    weekly_state: WeeklyQueueState,
    targets: dict[str, int],
    run_limit: int,
    publisher_cap: int,
) -> SelectionResult:
    """Select the complete scored pool under exact quotas and hard weekly caps."""

    state = WeeklyQueueState(
        region_counts=dict(weekly_state.region_counts),
        publisher_counts=dict(weekly_state.publisher_counts),
        existing_urls=set(weekly_state.existing_urls),
        existing_titles=list(weekly_state.existing_titles),
    )
    rejected: dict[str, int] = {}
    possible: list[CandidateResult] = []
    for candidate in candidates:
        if not candidate.eligible or not candidate.target_region:
            continue
        if candidate.article.canonical_url in state.existing_urls:
            _increment(rejected, "existing URL")
            continue
        if any(
            probable_same_event(candidate.article.title, title)
            for title in state.existing_titles
        ):
            _increment(rejected, "existing event")
            continue
        if state.publisher_counts.get(candidate.article.publisher_key, 0) >= publisher_cap:
            _increment(rejected, "publisher weekly cap")
            continue
        possible.append(candidate)

    # Highest-ranked representative survives each probable event cluster.
    deduped: list[CandidateResult] = []
    for candidate in sorted(possible, key=_final_rank_sort):
        if any(same_candidate_event(candidate, kept) for kept in deduped):
            _increment(rejected, "same event")
            continue
        deduped.append(candidate)

    winners: list[CandidateResult] = []
    remaining = deduped
    while remaining and len(winners) < run_limit:
        deficits = target_deficits(state.region_counts, targets)
        if not any(deficits.values()):
            break
        eligible_by_region: dict[str, list[CandidateResult]] = {}
        for region in TARGET_REGION_ORDER:
            if deficits.get(region, 0) <= 0:
                continue
            eligible_by_region[region] = [
                item
                for item in remaining
                if item.target_region == region
                and state.publisher_counts.get(item.article.publisher_key, 0)
                < publisher_cap
                and not any(same_candidate_event(item, winner) for winner in winners)
            ]
        regions = [region for region, items in eligible_by_region.items() if items]
        if not regions:
            break
        region = min(
            regions,
            key=lambda value: (
                len(eligible_by_region[value]) / deficits[value],
                TARGET_REGION_ORDER.index(value),
            ),
        )
        winner = sorted(eligible_by_region[region], key=_final_rank_sort)[0]
        winners.append(winner)
        state.region_counts[region] = state.region_counts.get(region, 0) + 1
        key = winner.article.publisher_key
        state.publisher_counts[key] = state.publisher_counts.get(key, 0) + 1
        state.existing_urls.add(winner.article.canonical_url)
        state.existing_titles.append(winner.article.title)
        remaining = [item for item in remaining if item is not winner]

    final_deficits = target_deficits(state.region_counts, targets)
    return SelectionResult(
        winners=winners,
        final_state=state,
        shortages=final_deficits,
        rejected_by_constraint=rejected,
    )


def normalize_event_title(title: str) -> set[str]:
    """Normalize a headline for bounded deterministic same-event comparison."""

    without_suffix = _PUBLISHER_SUFFIX_RE.sub("", title.casefold())
    return {
        token
        for token in _TOKEN_RE.findall(without_suffix)
        if token not in _STOP_WORDS and len(token) > 1
    }


def probable_same_event(left_title: str, right_title: str) -> bool:
    left = normalize_event_title(left_title)
    right = normalize_event_title(right_title)
    if not left or not right:
        return False
    similarity = len(left & right) / len(left | right)
    return similarity >= EVENT_TITLE_SIMILARITY_THRESHOLD


def same_candidate_event(left: CandidateResult, right: CandidateResult) -> bool:
    if left.article.canonical_url == right.article.canonical_url:
        return True
    return probable_same_event(left.article.title, right.article.title)


def _final_rank_sort(candidate: CandidateResult) -> tuple:
    enriched = candidate.enrichment
    published = candidate.article.published_date
    return (
        -candidate.queue_score,
        -(enriched.relevance_score if enriched else 0),
        -(candidate.source_quality or 0),
        -(_aware_utc(published).timestamp() if published else 0),
        candidate.article.canonical_url,
    )


def _title_text(property_value: dict[str, Any]) -> str:
    return "".join(
        item.get("plain_text", "") for item in property_value.get("title", [])
    ).strip()


def _increment(values: dict[str, int], key: str) -> None:
    values[key] = values.get(key, 0) + 1


def _aware_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

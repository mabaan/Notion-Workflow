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
    reported_location,
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

    @property
    def tier_counts(self) -> dict[str, int]:
        return {
            tier: sum(winner.selection_tier == tier for winner in self.winners)
            for tier in ("strict", "fallback")
        }


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
    allow_regional_overflow: bool = False,
    allow_fallback: bool = False,
) -> SelectionResult:
    """Preserve strict winners, then fill spare capacity from enriched fallback.

    Reserve strict coverage AND strict quality-overflow winners first. Otherwise
    fallback coverage could displace a strict overflow winner or consume its
    publisher allowance. Fallback then pursues remaining coverage before overflow.
    Legacy callers keep their existing strict selection unless explicitly opted in.
    """

    arguments = dict(targets=targets, publisher_cap=publisher_cap,
                     allow_regional_overflow=allow_regional_overflow)
    strict = _select_tier(
        candidates, weekly_state=weekly_state, run_limit=run_limit, **arguments,
    )
    if not allow_fallback or len(strict.winners) >= run_limit:
        return strict
    fallback_pool = [
        candidate for candidate in candidates
        if candidate.fallback_eligible
    ]
    fallback = _select_tier(
        fallback_pool, weekly_state=strict.final_state,
        run_limit=run_limit - len(strict.winners), tier="fallback",
        protected_winners=strict.winners, event_history=weekly_state.existing_titles,
        **arguments,
    )
    rejected = dict(strict.rejected_by_constraint)
    for reason, count in fallback.rejected_by_constraint.items():
        rejected[reason] = rejected.get(reason, 0) + count
    return SelectionResult(
        [*strict.winners, *fallback.winners], fallback.final_state,
        fallback.shortages, rejected,
    )


def _select_tier(
    candidates, *, weekly_state, targets, run_limit, publisher_cap,
    allow_regional_overflow, tier="strict", protected_winners=(), event_history=None,
) -> SelectionResult:
    """Use the existing coverage/score allocation and shared hard constraints."""

    state = WeeklyQueueState(
        region_counts=dict(weekly_state.region_counts),
        publisher_counts=dict(weekly_state.publisher_counts),
        existing_urls=set(weekly_state.existing_urls),
        existing_titles=list(weekly_state.existing_titles),
    )
    rejected: dict[str, int] = {}
    possible: list[CandidateResult] = []
    for candidate in candidates:
        candidate.regional_overflow = False
        candidate.selection_rejection_reason = ""
        candidate.selection_tier = None
        candidate.fallback_reason = ""
        if tier == "fallback":
            qualified = candidate.fallback_eligible
        else:
            qualified = candidate.eligible and bool(candidate.target_region)
        if not qualified:
            continue
        if tier == "strict" and allow_regional_overflow and candidate.enrichment.relevance_score < max(4, candidate.required_relevance_score or 4):
            candidate.selection_rejection_reason = "relevance below required threshold"
            _increment(rejected, candidate.selection_rejection_reason)
            continue
        if candidate.article.canonical_url in state.existing_urls:
            candidate.selection_rejection_reason = "existing URL"
            _increment(rejected, "existing URL")
            continue
        if any(
            probable_same_event(candidate.article.title, title)
            for title in (state.existing_titles if event_history is None else event_history)
        ):
            candidate.selection_rejection_reason = "existing event"
            _increment(rejected, "existing event")
            continue
        if any(same_candidate_event(candidate, winner) for winner in protected_winners):
            candidate.selection_rejection_reason = "same event"
            _increment(rejected, "same event")
            continue
        if state.publisher_counts.get(candidate.article.publisher_key, 0) >= publisher_cap:
            candidate.selection_rejection_reason = "publisher weekly cap"
            _increment(rejected, "publisher weekly cap")
            continue
        possible.append(candidate)

    # Highest-ranked representative survives each probable event cluster.
    deduped: list[CandidateResult] = []
    for candidate in sorted(possible, key=_final_rank_sort):
        if any(same_candidate_event(candidate, kept) for kept in deduped):
            candidate.selection_rejection_reason = "same event"
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

    # Coverage has had first claim on every slot. Only already-qualified
    # candidates enter this pass; classifier scores never establish eligibility.
    if allow_regional_overflow:
        for candidate in sorted(remaining, key=_final_rank_sort):
            if len(winners) >= run_limit:
                break
            if state.publisher_counts.get(candidate.article.publisher_key, 0) >= publisher_cap:
                continue
            if any(same_candidate_event(candidate, winner) for winner in winners):
                continue
            candidate.regional_overflow = True
            winners.append(candidate)
            region = candidate.target_region
            state.region_counts[region] = state.region_counts.get(region, 0) + 1
            key = candidate.article.publisher_key
            state.publisher_counts[key] = state.publisher_counts.get(key, 0) + 1
            state.existing_urls.add(candidate.article.canonical_url)
            state.existing_titles.append(candidate.article.title)

    winner_ids = {id(winner) for winner in winners}
    for winner in winners:
        winner.selection_tier = tier
        if tier == "fallback":
            winner.fallback_reason = (
                f"final relevance {winner.enrichment.relevance_score} below strict threshold "
                f"{winner.required_relevance_score or 4}; registered publisher; "
                "final relevance and significance >= 3; spare capacity after strict selection"
            )
    for candidate in deduped:
        if id(candidate) in winner_ids:
            continue
        if state.publisher_counts.get(candidate.article.publisher_key, 0) >= publisher_cap:
            candidate.selection_rejection_reason = "publisher weekly cap"
        elif any(same_candidate_event(candidate, winner) for winner in winners):
            candidate.selection_rejection_reason = "same event"
        else:
            candidate.selection_rejection_reason = "run capacity" if len(winners) >= run_limit else "regional coverage complete"

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
    a, b = left.article, right.article
    a_location, _ = reported_location(a.title, a.snippet)
    b_location, _ = reported_location(b.title, b.snippet)
    # A common company/topic must not merge projects in different countries.
    if a_location and b_location and a_location != b_location:
        return False
    a_measures, b_measures = _event_measures(a.title), _event_measures(b.title)
    if any(a_measures[unit].isdisjoint(b_measures[unit]) for unit in a_measures.keys() & b_measures.keys()):
        return False
    if probable_same_event(a.title, b.title):
        return True
    return _same_policy_announcement(a, b, a_location, b_location)


_EVENT_WORD_FORMS = {
    "grow": "production", "grows": "production", "growing": "production",
    "locally": "local", "updated": "update", "updates": "update",
    "revised": "update", "revises": "update", "revision": "update",
    "approved": "approve", "approves": "approve", "approval": "approve",
    "adopted": "adopt", "adopts": "adopt", "announced": "announce",
    "announces": "announce", "launched": "launch", "launches": "launch",
    "policies": "policy", "regulations": "regulation", "plans": "plan",
    "targets": "target",
}
_POLICY_WORDS = {"policy", "strategy", "regulation", "law", "plan"}
_ANNOUNCEMENT_WORDS = {"update", "approve", "adopt", "announce", "launch"}


def _event_measures(text):
    """Compare like units; capacity in one report is not a conflicting cost."""

    measures = {}
    for number, unit in re.findall(
        r"\b(\d[\d,]*(?:\.\d+)?)\s*(%|percent\b|per cent\b|gwh\b|mwh\b|gw\b|mw\b)",
        text.casefold(),
    ):
        value = float(number.replace(",", ""))
        if unit.startswith("g"):
            value *= 1000
            unit = "m" + unit[1:]
        if unit in {"percent", "per cent"}:
            unit = "%"
        measures.setdefault(unit, set()).add(value)
    return measures


def _event_tokens(text):
    return {
        _EVENT_WORD_FORMS.get(token, token) for token in _TOKEN_RE.findall(text.casefold())
        if token not in _STOP_WORDS | {"more", "under"} and len(token) > 1
    }


def _event_title(article):
    # Strip the actual source suffix, including long multi-part publisher names.
    return re.split(
        r"\s+[-|]\s+" + re.escape(article.source_name) + r"(?:\b|$)",
        article.title, maxsplit=1, flags=re.IGNORECASE,
    )[0] if article.source_name else article.title


def _same_policy_announcement(left, right, left_location, right_location):
    """Require a shared policy action, event country, time and strong text overlap.

    This is deliberately narrower than topic similarity. Sparse metadata that
    cannot establish these anchors does not create a new event match.
    """

    if not left_location or left_location != right_location:
        return False
    if not left.published_date or not right.published_date:
        return False
    if abs((_aware_utc(left.published_date) - _aware_utc(right.published_date)).total_seconds()) > 3 * 86400:
        return False
    a, b = _event_tokens(_event_title(left)), _event_tokens(_event_title(right))
    shared = a & b
    if not a & _POLICY_WORDS or not b & _POLICY_WORDS or not shared & _ANNOUNCEMENT_WORDS:
        return False
    if shared & _POLICY_WORDS and min(len(a), len(b)) >= 6 and len(shared) / min(len(a), len(b)) >= 0.85:
        return True
    if len(shared) < 3 or not left.snippet or not right.snippet:
        return False
    a_evidence, b_evidence = _event_tokens(left.snippet), _event_tokens(right.snippet)
    overlap = a_evidence & b_evidence
    return len(overlap) >= 12 and len(overlap) / min(len(a_evidence), len(b_evidence)) >= 0.9


def _final_rank_sort(candidate: CandidateResult) -> tuple:
    enriched = candidate.enrichment
    published = candidate.article.published_date
    return (
        -candidate.queue_score,
        -(enriched.relevance_score if enriched else 0),
        -(_editorial_significance(enriched) if enriched else 0),
        -(candidate.source_quality or 0),
        -(_aware_utc(published).timestamp() if published else 0),
        candidate.article.canonical_url,
    )


def _editorial_significance(enriched) -> int:
    """Keep deterministic ranking compatible with older enrichment objects."""

    value = getattr(enriched, "editorial_significance", 3)
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 3
    return max(1, min(5, score))


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

"""Offline regressions for strict-first selection of already-enriched articles."""

from collections import Counter
from dataclasses import replace
import json

import pytest

from research_automation.models.article import EnrichedArticle
from research_automation.pipeline.candidate_audit import build_candidate_audit
from research_automation.pipeline.candidate_ranking import calculate_queue_score
from research_automation.pipeline.ingestion import print_ingestion_report
from research_automation.pipeline.selection import WeeklyQueueState, select_final_candidates

from test_ingestion import _settings
from test_luna_selection import TARGETS, Enricher, article, candidate, factory, regional_pool


def fallback(key, region="Global", *, score=3, significance=4, publisher=None, quality=8):
    result = candidate(key, region, publisher=publisher, score=score, significance=significance)
    result.enrichment_attempted = True
    result.rejection_reason = "relevance below 4"
    result.source_quality = quality
    result.queue_score = calculate_queue_score(score, quality, significance)
    return result


def select(pool, *, limit=12, state=None, cap=2, targets=None, enabled=True):
    return select_final_candidates(
        pool, weekly_state=state or WeeklyQueueState(), targets=targets or TARGETS,
        run_limit=limit, publisher_cap=cap, allow_regional_overflow=True,
        allow_fallback=enabled,
    )


def test_twelve_strict_candidates_use_no_fallback():
    strict = regional_pool(TARGETS)
    soft = [fallback(f"soft{i}") for i in range(5)]
    before = select(strict, enabled=False)
    after = select([*soft, *strict])
    assert after.winners == before.winners
    assert after.final_state == before.final_state
    assert after.tier_counts == {"strict": 12, "fallback": 0}
    assert all(item.selection_tier is None for item in soft)


def test_four_strict_plus_five_fallback_returns_nine():
    strict = regional_pool({"Global": 1, "UAE": 1, "KSA": 1, "Egypt": 1})
    soft = [fallback(f"soft{i}") for i in range(5)]
    result = select([*soft, *strict])
    assert result.tier_counts == {"strict": 4, "fallback": 5}
    assert len(result.winners) == 9
    assert {id(w) for w in result.winners[:4]} == {id(w) for w in strict}
    assert all(item.rejection_reason == "relevance below 4" and not item.eligible for item in soft)
    assert all(item.fallback_reason for item in soft)


def test_eight_qualified_articles_return_eight_instead_of_forcing_twelve():
    pool = regional_pool({"Global": 1, "UAE": 1, "KSA": 1, "Egypt": 1})
    pool += [fallback(f"soft{i}") for i in range(4)]
    assert len(select(pool, limit=12).winners) == 8


@pytest.mark.parametrize("relevance,significance,registered,expected", [
    (3, 4, True, True), (3, 3, True, True), (3, 2, True, False),
    (2, 5, True, False), (1, 5, True, False),
    (3, 5, False, False), (4, 5, False, False),
])
def test_fallback_quality_floors(relevance, significance, registered, expected):
    item = fallback("floor", score=relevance, significance=significance)
    if not registered:
        item.article.source_page_id = ""
        item.required_relevance_score = 5
        item.rejection_reason = "relevance below 5"
    assert item.fallback_eligible is expected
    assert bool(select([item]).winners) is expected


@pytest.mark.parametrize("region", [None, "", "Out of Scope/Unclear", "Jordan"])
def test_fallback_requires_a_valid_region(region):
    assert not select([fallback("region", region)]).winners


def test_strict_beats_higher_queue_score_fallback_for_capacity():
    strict = candidate("strict", "Global", score=4, significance=1)
    strict.source_quality = 0
    strict.queue_score = calculate_queue_score(4, 0, 1)
    soft = fallback("soft", "Egypt", significance=5, quality=10)
    assert soft.queue_score > strict.queue_score
    result = select([soft, strict], limit=1)
    assert result.winners == [strict]
    assert result.tier_counts == {"strict": 1, "fallback": 0}


def test_strict_overflow_is_reserved_before_fallback_coverage_and_publisher_cap():
    state = WeeklyQueueState(region_counts={**dict.fromkeys(TARGETS, 0), "Global": 3})
    strict = candidate("strict-overflow", publisher="shared")
    soft = fallback("soft-coverage", "Egypt", publisher="shared", significance=5)
    result = select([soft, strict], state=state, limit=2, cap=1)
    assert result.winners == [strict]
    assert strict.regional_overflow
    assert soft.selection_rejection_reason == "publisher weekly cap"


def test_fallback_coverage_precedes_higher_scoring_fallback_overflow():
    strict = candidate("strict", "Global")
    missing = fallback("missing", "KSA", significance=3)
    overflow = fallback("overflow", "Global", significance=5)
    assert missing.queue_score < overflow.queue_score
    result = select([overflow, strict, missing], limit=2, targets=dict.fromkeys(TARGETS, 1))
    assert result.winners == [strict, missing]
    assert result.shortages["KSA"] == 0
    assert not missing.regional_overflow


def test_fallback_can_fill_quality_overflow_after_coverage():
    strict = regional_pool({"Global": 3})
    low = fallback("low", significance=3)
    high = fallback("high", significance=5)
    result = select([low, high, *strict], limit=5)
    assert result.winners[-2:] == [high, low]
    assert all(w.regional_overflow for w in result.winners[-2:])
    assert result.tier_counts == {"strict": 3, "fallback": 2}
    assert result.shortages["KSA"] == 3
    assert high.queue_score == calculate_queue_score(3, 8, 5)


def test_weekly_publisher_cap_carries_across_tiers():
    strict = candidate("strict", publisher="shared")
    soft = fallback("soft", "Egypt", publisher="shared")
    state = WeeklyQueueState(publisher_counts={"shared": 1})
    result = select([soft, strict], state=state)
    assert result.winners == [strict]
    assert result.final_state.publisher_counts["shared"] == 2


def test_fallback_publisher_cap_keeps_strongest_representative():
    low = fallback("low", publisher="shared", significance=3)
    high = fallback("high", publisher="shared", significance=5)
    result = select([low, high], state=WeeklyQueueState(publisher_counts={"shared": 1}))
    assert result.winners == [high]
    assert result.final_state.publisher_counts["shared"] == 2


def test_fallback_same_event_dedup_keeps_strongest():
    low, high = fallback("low", significance=3), fallback("high", significance=5)
    high.article.title = low.article.title = "Egypt approves national irrigation infrastructure programme"
    result = select([low, high])
    assert result.winners == [high]
    assert low.selection_rejection_reason == "same event"


def test_strict_event_representative_cannot_be_replaced_by_fallback():
    strict = candidate("strict", significance=1)
    soft = fallback("soft", significance=5)
    strict.article.title = soft.article.title = "Egypt approves national irrigation infrastructure programme"
    result = select([soft, strict])
    assert result.winners == [strict]
    assert soft.selection_rejection_reason == "same event"


def test_existing_queue_event_and_processed_url_exclude_fallback():
    event, processed = fallback("event"), fallback("processed")
    state = WeeklyQueueState(existing_titles=[event.article.title], existing_urls={processed.article.canonical_url})
    result = select([event, processed], state=state)
    assert not result.winners
    assert event.selection_rejection_reason == "existing event"
    assert processed.selection_rejection_reason == "existing URL"


def test_different_capacity_projects_still_survive_across_tiers():
    strict = candidate("strict", "Egypt", title="Egypt company commissions 200 MW solar project near Cairo")
    soft = fallback("soft", "Egypt")
    soft.article.title = "Egypt company commissions 400 MW solar project near Cairo"
    assert select([strict, soft]).winners == [strict, soft]


@pytest.mark.parametrize("limit", [0, 1, 2, 5, 12])
def test_requested_limit_is_only_a_maximum(limit):
    pool = [candidate("strict"), fallback("soft-one"), fallback("soft-two")]
    assert len(select(pool, limit=limit).winners) == min(3, limit)


@pytest.mark.parametrize("reason", [
    "duplicate URL", "existing event", "Luna classified irrelevant",
    "self-published content after URL resolution", "enrichment failed: provider error",
])
def test_fallback_never_overrides_another_rejection(reason):
    item = fallback("other-rejection")
    item.rejection_reason = reason
    assert not select([item]).winners


def test_explicit_publication_failure_blocks_fallback():
    item = fallback("factual-failure")
    item.publication_failure_reason = "Reported project was retracted; supplied evidence contradicts the claim"
    assert not select([item]).winners


def test_objective_failure_and_invalid_url_block_fallback():
    failed, invalid = fallback("failed"), fallback("invalid")
    failed.objective_cleanup_reason = "previously processed article"
    invalid.article.evidence_retrieval_status = "invalid_url"
    assert not select([failed, invalid]).winners


def test_missing_full_text_is_not_a_fabricated_factual_failure():
    item = fallback("blocked")
    item.article.evidence_retrieval_status = "blocked"
    assert select([item]).winners == [item]


def test_unenriched_candidates_cannot_enter_fallback():
    item = fallback("not-enriched")
    item.enrichment = None
    assert not select([item]).winners


def test_two_tier_dry_run_audit_and_console_use_existing_enrichments(factory, tmp_path):
    scores = {f"strict{i}": (4, 2) for i in range(4)}
    scores.update({f"soft{i}": (3, 4) for i in range(5)})
    scores.update({"too-incidental": (2, 5), "too-minor": (3, 2)})
    pool = [article(key) for key in scores]
    by_title = {item.title: scores[key] for item, key in zip(pool, scores)}

    class Scored(Enricher):
        def enrich_article(self, item):
            self.calls.append(item.title)
            score, significance = by_title[item.title]
            return EnrichedArticle("Supported facts", "Mission consequence", score,
                                   editorial_significance=significance, region=["Global"])

    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna")
    settings.local_state_path.mkdir()
    settings.seen_articles_path.write_text('{"old-hash": {"notion_page_id": "old-page"}}', encoding="utf-8")
    before = settings.seen_articles_path.read_bytes()
    run = factory(pool, settings=settings, llm=Scored(), classify=lambda _: ("Relevant", 5, "Global"))
    assert run.report.selection.tier_counts == {"strict": 4, "fallback": 5}
    assert len(run.llm.calls) == len(pool)
    assert set(Counter(run.llm.calls).values()) == {1}
    assert len(run.requests) == 1
    assert run.notion.creates == run.notion.updates == []
    assert settings.seen_articles_path.read_bytes() == before
    audit = build_candidate_audit(run.report)
    assert audit["selection_counts"] == {"strict": 4, "fallback": 5, "total": 9}
    rows = [row for row in audit["candidates"] if row["selection_tier"] == "fallback"]
    assert len(rows) == 5
    for row in rows:
        assert row["classification_relevance"] == 5
        assert row["relevance"] == 3
        assert row["editorial_significance"] == 4
        assert row["publisher_rating"] == 8
        assert row["queue_score"] == calculate_queue_score(3, 8, 4)
        assert row["region"] == "Global"
        assert row["fallback_qualified"] and row["qualified"] and row["selected"]
        assert not row["strict_qualified"]
        assert row["strict_rejection_reason"] == "relevance below 4"
        assert row["final_rejection_reason"] == ""
        assert "below strict threshold 4" in row["fallback_reason"]
        assert "selected via fallback" in row["reason"]
    saved = json.loads(run.report.audit_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert saved == json.loads(json.dumps(audit))  # Request ID tuples serialize as JSON arrays.
    markdown = run.report.audit_path.read_text(encoding="utf-8")
    assert "Selection tier" in markdown and "Publisher rating / queue score / region" in markdown
    output = []
    print_ingestion_report(run.report, output=output.append)
    assert {"Strict selections: 4", "Fallback selections: 5", "Total selections: 9"} <= set(output)
    assert sum("selection_tier=fallback" in line for line in output) == 5
    assert "Strict qualification rejected [relevance below 4]: 7" in output


@pytest.mark.parametrize("resolved", ["Egypt", "Out of Scope/Unclear"])
def test_fallback_geography_must_be_resolved_by_existing_enrichment(factory, resolved):
    run = factory([article("unclear")],
                  classify=lambda _: ("Borderline", 3, "Out of Scope/Unclear"),
                  llm=Enricher(score=3, significance=4, region=resolved))
    assert len(run.llm.calls) == 1
    result, = run.report.evaluation.results
    assert result.rejection_reason == "relevance below 4"
    assert bool(run.report.selection.winners) == (resolved == "Egypt")
    if resolved == "Egypt":
        assert result.selection_tier == "fallback" and result.article.region == ["Egypt"]


@pytest.mark.parametrize("score,expected", [(3, False), (4, False), (5, True)])
def test_unknown_publisher_production_path_retains_threshold_five(factory, score, expected):
    run = factory([article("unknown", registered=False)], llm=Enricher(score=score, significance=5))
    assert bool(run.report.selection.winners) is expected
    assert run.report.selection.tier_counts["fallback"] == 0
    assert run.report.evaluation.results[0].required_relevance_score == 5


def test_fallback_does_not_shorten_strict_enrichment_opportunities(factory):
    run = factory([article(f"feed-{i:03}") for i in range(60)], llm=Enricher(score=3, significance=4))
    assert len(run.llm.calls) == 48
    assert len({title for title, _ in run.llm.calls}) == 48
    assert run.report.enrichment_budget == {"initial": 32, "maximum": 48, "backfill_batch": 8, "attempted": 48}
    assert run.report.selection.tier_counts == {"strict": 0, "fallback": 12}

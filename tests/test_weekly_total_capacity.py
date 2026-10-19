"""Offline weekly-total safety, shared-tier limits and repeated-ingestion tests."""

from dataclasses import replace
import json

import pytest

from research_automation.pipeline import ingestion
from research_automation.pipeline.candidate_audit import build_candidate_audit
from research_automation.pipeline.ingestion import IngestionOptions, print_ingestion_report, run_ingestion
from research_automation.pipeline.selection import (
    WeeklyQueueState, select_final_candidates, weekly_capacity_snapshot,
)
from research_automation.utils.regions import target_deficits

from test_ingestion import FakeNotion, _settings
from test_luna_selection import TARGETS, article, candidate, factory, regional_pool
from test_selection import _page
from test_two_tier_selection import fallback


NINE_EXISTING = {"Global": 6, "UAE": 1, "KSA": 1, "Egypt": 1}


def settings_for_week(path, mode="luna"):
    return replace(
        _settings(path), article_selection_mode=mode,
        article_queue_weekly_target_global=3, article_queue_weekly_target_uae=4,
        article_queue_weekly_target_ksa=3, article_queue_weekly_target_egypt=2,
    )


def pages_with_counts(counts):
    return [_page(f"Existing weekly record {region} {i}", region,
                  f"https://old.example/{region}/{i}", f"old-{region}-{i}")
            for region, count in counts.items() for i in range(count)]


def select(pool, counts, limit=12):
    return select_final_candidates(
        pool, weekly_state=WeeklyQueueState(region_counts=dict(counts)), targets=TARGETS,
        run_limit=limit, publisher_cap=2, allow_regional_overflow=True, allow_fallback=True,
    )


@pytest.mark.parametrize("counts,limit,expected", [
    ({}, 12, 12),
    (NINE_EXISTING, 12, 3),
    (NINE_EXISTING, 2, 2),
    ({"Global": 9, "UAE": 1, "KSA": 1, "Egypt": 1}, 12, 0),
    ({"Global": 11, "UAE": 1, "KSA": 1, "Egypt": 1}, 12, 0),
    ({"Global": 2}, 5, 5),
    (NINE_EXISTING, 0, 0),
])
def test_final_selector_caps_new_winners_by_actual_weekly_total(counts, limit, expected):
    state = WeeklyQueueState(region_counts=dict(counts))
    capacity = weekly_capacity_snapshot(state, TARGETS, limit)
    result = select(regional_pool(TARGETS), counts, limit)
    assert capacity == {
        "weekly_total_target": 12, "existing_weekly_total": sum(counts.values()),
        "remaining_weekly_capacity": max(0, 12 - sum(counts.values())),
        "requested_run_limit": limit, "effective_run_capacity": expected,
    }
    assert len(result.winners) == expected
    assert sum(result.final_state.region_counts.values()) == sum(counts.values()) + expected
    assert state.region_counts == counts  # Planning never mutates the loaded state.


def test_target_is_derived_from_configuration_not_a_constant_twelve():
    targets = {"Global": 5, "UAE": 5, "KSA": 5, "Egypt": 5}
    state = WeeklyQueueState(region_counts=dict(NINE_EXISTING))
    snapshot = weekly_capacity_snapshot(state, targets, 12)
    assert snapshot["weekly_total_target"] == 20 and snapshot["remaining_weekly_capacity"] == 11
    result = select_final_candidates(
        regional_pool(TARGETS), weekly_state=state, targets=targets, run_limit=12,
        publisher_cap=2, allow_regional_overflow=True,
    )
    assert len(result.winners) == 11


def test_existing_regional_overflow_counts_against_total_not_positive_deficits():
    state = WeeklyQueueState(region_counts=dict(NINE_EXISTING))
    assert sum(target_deficits(state.region_counts, TARGETS).values()) == 6
    assert weekly_capacity_snapshot(state, TARGETS, 12)["remaining_weekly_capacity"] == 3
    assert len(select(regional_pool(TARGETS), NINE_EXISTING).winners) == 3


def test_coverage_preferences_and_strict_quality_overflow_share_remaining_capacity():
    uae = candidate("uae-plant", "UAE", score=5)
    egypt = candidate("egypt-water", "Egypt", score=5)
    global_story = candidate("global-minerals", "Global", score=5)
    weak_ksa = fallback("weak-ksa", "KSA", score=3, significance=2)
    result = select([weak_ksa, global_story, egypt, uae], NINE_EXISTING)
    assert {id(r) for r in result.winners} == {id(uae), id(egypt), id(global_story)}
    assert global_story.regional_overflow and not uae.regional_overflow and not egypt.regional_overflow
    assert result.final_state.region_counts == {"Global": 7, "UAE": 2, "KSA": 1, "Egypt": 2}
    assert sum(result.final_state.region_counts.values()) == 12
    assert result.shortages["KSA"] == 2


def test_unfilled_regions_do_not_prevent_quality_overflow_within_total_cap():
    pool = regional_pool({"Global": 5})
    result = select(pool, NINE_EXISTING)
    assert len(result.winners) == 3 and all(r.regional_overflow for r in result.winners)
    assert result.final_state.region_counts == {"Global": 9, "UAE": 1, "KSA": 1, "Egypt": 1}
    assert result.shortages == {"Global": 0, "UAE": 3, "KSA": 2, "Egypt": 1}


@pytest.mark.parametrize("strict_count,expected", [(4, {"strict": 3, "fallback": 0}),
                                                    (2, {"strict": 2, "fallback": 1})])
def test_strict_and_fallback_share_one_weekly_capacity(strict_count, expected):
    strict = regional_pool({"Global": strict_count})
    soft = [fallback(f"soft-{key}", "Egypt") for key in ("alpha", "bravo", "charlie", "delta")]
    result = select([*soft, *strict], NINE_EXISTING)
    assert result.tier_counts == expected and len(result.winners) == 3
    assert sum(result.final_state.region_counts.values()) == 12


def test_sequential_selection_states_stop_at_eight_then_four_then_zero():
    pool = regional_pool(TARGETS)
    state = WeeklyQueueState()
    sizes = []
    for limit in (8, 12, 12):
        result = select_final_candidates(
            pool, weekly_state=state, targets=TARGETS, run_limit=limit,
            publisher_cap=2, allow_regional_overflow=True, allow_fallback=True,
        )
        sizes.append(len(result.winners))
        state = result.final_state
    assert sizes == [8, 4, 0]
    assert sum(state.region_counts.values()) == len(state.existing_urls) == 12


@pytest.mark.parametrize("counts,limit,expected", [
    (NINE_EXISTING, 12, 3), (NINE_EXISTING, 2, 2), ({"Global": 2}, 5, 5),
])
def test_luna_uses_effective_capacity_to_stop_enrichment_and_report(factory, tmp_path, counts, limit, expected):
    settings = settings_for_week(tmp_path / "state")
    notion = FakeNotion(article_pages=pages_with_counts(counts))
    pool = [article(key) for key in (
        "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
        "india", "juliet", "kilo", "lima",
    )]
    run = factory(pool, settings=settings, notion=notion, options=IngestionOptions(dry_run=True, limit=limit))
    assert len(run.llm.calls) == len(run.report.selection.winners) == expected
    assert run.report.weekly_capacity["effective_run_capacity"] == expected
    assert run.report.enrichment_budget == {"initial": 32, "maximum": 48, "backfill_batch": 8, "attempted": expected}
    assert notion.creates == notion.updates == [] and not settings.seen_articles_path.exists()
    if counts == NINE_EXISTING and limit == 12:
        lines = []
        print_ingestion_report(run.report, output=lines.append)
        for line in ("Weekly article target: 12", "Existing weekly total: 9", "Remaining weekly capacity: 3",
                     "Requested run limit: 12", "Effective run capacity: 3"):
            assert line in lines
            assert line in run.report.audit_path.read_text(encoding="utf-8")
        audit = build_candidate_audit(run.report)
        assert audit["weekly_capacity"] == run.report.weekly_capacity
        saved = json.loads(run.report.audit_path.with_suffix(".json").read_text(encoding="utf-8"))
        assert saved["weekly_capacity"] == run.report.weekly_capacity


@pytest.mark.parametrize("mode", ["luna", "deterministic"])
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("existing", [12, 14])
def test_full_week_skips_all_paid_work_and_notion_writes(tmp_path, monkeypatch, mode, dry_run, existing):
    counts = {"Global": existing - 3, "UAE": 1, "KSA": 1, "Egypt": 1}
    notion = FakeNotion(article_pages=pages_with_counts(counts))
    settings = settings_for_week(tmp_path / "state", mode)
    settings.local_state_path.mkdir()
    settings.seen_articles_path.write_text('{"unchanged": {"notion_page_id": "old-page"}}', encoding="utf-8")
    before = settings.seen_articles_path.read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("A full week must skip setup writes, collection, discovery, retrieval and both paid stages")

    monkeypatch.setattr(ingestion, "ensure_current_weekly_pages", forbidden)
    monkeypatch.setattr(ingestion, "ArticleClassifier", forbidden)
    monkeypatch.setattr(ingestion, "LlmClient", forbidden)
    monkeypatch.setattr(notion, "create_page", forbidden)
    monkeypatch.setattr(notion, "update_page", forbidden)
    report = run_ingestion(
        settings, IngestionOptions(dry_run=dry_run, all_sources=True, limit=12), notion=notion,
        collector=forbidden, discovery_factory=forbidden, retrieve_article=forbidden,
        direct_collector=forbidden, output=lambda _: None,
    )
    assert report.weekly_capacity == {
        "weekly_total_target": 12, "existing_weekly_total": existing, "remaining_weekly_capacity": 0,
        "requested_run_limit": 12, "effective_run_capacity": 0,
    }
    assert report.initial_deficits == {"Global": 0, "UAE": 3, "KSA": 2, "Egypt": 1}
    assert report.selection.winners == [] and report.pages_created == 0
    assert report.collected_count == report.discovered_count == 0 and report.attempts == []
    assert report.evaluation.classification_reports == [] and report.evaluation.results == []
    if mode == "luna":
        assert report.enrichment_budget["attempted"] == 0
    assert notion.creates == notion.updates == []
    assert settings.seen_articles_path.read_bytes() == before
    assert build_candidate_audit(report)["weekly_capacity"]["effective_run_capacity"] == 0


def test_repeated_mocked_live_runs_load_existing_queue_and_stop_at_weekly_target(factory, tmp_path):
    class QueueNotion(FakeNotion):
        def create_page(self, database_id, properties, children=None):
            page = super().create_page(database_id, properties, children)
            if database_id == "article-db":
                self.article_pages.append(page)
            return page

    settings, notion = settings_for_week(tmp_path / "state"), QueueNotion()
    qualified = regional_pool(TARGETS)
    pool = [result.article for result in qualified]
    regions = {result.article.title: result.target_region for result in qualified}
    reports = []
    for limit in (8, 12, 12):
        before_writes = len(notion.creates), len(notion.updates)
        run = factory(pool, settings=settings, notion=notion, options=IngestionOptions(limit=limit, all_sources=True),
                      classify=lambda row: ("Relevant", 4, regions[row["title"]]))
        reports.append(run.report)
        if run.report.weekly_capacity["remaining_weekly_capacity"] == 0:
            assert (len(notion.creates), len(notion.updates)) == before_writes
            assert not run.requests and not run.llm.calls
    assert [report.pages_created for report in reports] == [8, 4, 0]
    assert [report.weekly_capacity["existing_weekly_total"] for report in reports] == [0, 8, 12]
    assert len(notion.article_pages) == 12
    assert len({page["properties"]["Canonical URL"]["url"] for page in notion.article_pages}) == 12

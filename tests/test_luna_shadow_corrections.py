"""Offline regressions for the first real shadow run's downstream failures."""

from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_automation.clients.llm_client import LlmClient
from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.candidate import CandidateResult
from research_automation.pipeline.selection import (
    WeeklyQueueState, probable_same_event, same_candidate_event, select_final_candidates,
)
from test_ingestion import FakeNotion, NOW, _settings
from test_luna_selection import Enricher, article, candidate, factory, select
from test_selection import _page


FIXTURE = json.loads((Path(__file__).parent / "fixtures/luna_shadow_qualified.json").read_text(encoding="utf-8"))


def test_four_reuters_candidates_can_be_enriched_but_only_best_two_selected(factory):
    pool = [article(key, publisher="Reuters", quality=9) for key in ("alpha", "bravo", "charlie", "delta")]

    class Scored(Enricher):
        def enrich_article(self, item):
            self.calls.append(item.title)
            score = 5 if item.title in {pool[2].title, pool[3].title} else 4
            return EnrichedArticle("summary", "mission", score, region=["Global"], editorial_significance=4)

    run = factory(pool, llm=Scored())
    assert len(run.llm.calls) == 4
    assert {winner.article.title for winner in run.report.selection.winners} == {pool[2].title, pool[3].title}
    assert run.report.selection.final_state.publisher_counts == {"Reuters": 2}
    assert "publisher weekly cap" not in run.report.evaluation.rejection_counts


def test_later_reuters_candidates_qualify_after_first_two_fail(factory):
    class Later(Enricher):
        def enrich_article(self, item):
            self.calls.append(item.title)
            score = 2 if len(self.calls) <= 2 else 4
            return EnrichedArticle("summary", "mission", score, region=["Global"])

    run = factory([article(key, publisher="Reuters") for key in ("alpha", "bravo", "charlie", "delta")], llm=Later())
    assert len(run.llm.calls) == 4
    assert len(run.report.selection.winners) == 2
    assert {winner.article.title for winner in run.report.selection.winners} == set(run.llm.calls[2:])


def test_existing_weekly_publisher_cap_applies_only_at_final_selection(factory):
    notion = FakeNotion(article_pages=[
        _page("Existing unrelated weekly story alpha", "Global", "https://old.example/a", "Reuters"),
        _page("Existing unrelated weekly story bravo", "Global", "https://old.example/b", "Reuters"),
    ])
    run = factory([article(key, publisher="Reuters") for key in ("alpha", "bravo", "charlie", "delta")], notion=notion)
    assert len(run.llm.calls) == 4
    assert run.report.selection.winners == []
    assert run.report.selection.final_state.publisher_counts["Reuters"] == 2
    assert notion.creates == notion.updates == []


@pytest.mark.parametrize("other_decision,other_score", [("Relevant", 4), ("Borderline", 3)])
def test_soft_diversity_prevents_score_five_publisher_monopoly(factory, tmp_path, other_decision, other_score):
    pool = [article(f"reuters-{i}", publisher="Reuters") for i in range(12)]
    pool += [article("other", publisher="Other")]
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna",
                       article_enrichment_initial_budget=2, article_enrichment_max_budget=2)
    run = factory(pool, settings=settings, classify=lambda r: (
        ("Relevant", 5, "Global") if r["publisher"] == "Reuters" else (other_decision, other_score, "Global")
    ))
    assessed = [r.article.publisher_key for r in run.report.evaluation.results if r.enrichment_attempted]
    assert sorted(assessed) == ["Other", "Reuters"]


@pytest.mark.parametrize("positive_attempts,expected_attempts,expected_winners", [
    (set(range(1, 12)) | {32}, 32, 12),
    (set(range(1, 9)) | set(range(37, 41)), 40, 12),
    (set(range(1, 9)), 48, 8),
    (set(range(1, 12)) | {35}, 35, 12),
])
def test_adaptive_budget_stops_at_viable_unique_capacity_or_maximum(factory, tmp_path, positive_attempts, expected_attempts, expected_winners):
    class Conditional(Enricher):
        def enrich_article(self, item):
            self.calls.append(item.title)
            score = 4 if len(self.calls) in positive_attempts else 3
            return EnrichedArticle("summary", "mission", score, region=["Global"], editorial_significance=4)

    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna",
                       article_queue_weekly_target_global=3, article_queue_weekly_target_uae=4,
                       article_queue_weekly_target_ksa=3, article_queue_weekly_target_egypt=2)
    run = factory([article(f"feed-{i:03}") for i in range(60)], llm=Conditional(), settings=settings)
    assert len(run.llm.calls) == expected_attempts
    assert len(set(run.llm.calls)) == expected_attempts
    assert run.report.selection.tier_counts["strict"] == expected_winners
    assert len(run.report.selection.winners) == 12
    assert run.report.selection.tier_counts["fallback"] == 12 - expected_winners
    assert run.report.enrichment_budget == {"initial": 32, "maximum": 48, "backfill_batch": 8, "attempted": expected_attempts}
    assert run.notion.creates == run.notion.updates == []
    assert not run.settings.seen_articles_path.exists()
    if expected_attempts == 48:
        assert run.report.evaluation.rejection_counts["enrichment budget exhausted"] == 12


def test_adaptive_budget_counts_failed_calls_and_clamps_last_batch(factory, tmp_path):
    class Failing(Enricher):
        def enrich_article(self, item):
            self.calls.append(item.title)
            raise RuntimeError("Offline failure")

    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna",
                       article_enrichment_initial_budget=32, article_enrichment_max_budget=43)
    run = factory([article(f"feed-{i:03}") for i in range(60)], settings=settings, llm=Failing())
    assert len(run.llm.calls) == 43
    assert len(set(run.llm.calls)) == 43
    assert run.report.evaluation.rejection_counts["enrichment budget exhausted"] == 17


def test_no_backfill_when_only_explicitly_irrelevant_articles_remain(factory, tmp_path):
    pool = [article(f"positive-{i:03}") for i in range(32)] + [article(f"irrelevant-{i:03}") for i in range(8)]
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna",
                       article_queue_weekly_target_global=3, article_queue_weekly_target_uae=4,
                       article_queue_weekly_target_ksa=3, article_queue_weekly_target_egypt=2)
    run = factory(pool, settings=settings, llm=Enricher(score=3), classify=lambda r: (
        ("Irrelevant", 1, "Global") if "irrelevant-" in r["title"] else ("Relevant", 4, "Global")
    ))
    assert len(run.llm.calls) == 32
    assert run.report.selection.tier_counts == {"strict": 0, "fallback": 12}


def test_stop_condition_uses_unique_events_and_final_publisher_caps(factory):
    # Twelve qualified stories from one publisher cannot fill twelve final slots.
    pool = [article(f"reuters-{i:03}", publisher="Reuters") for i in range(36)]
    run = factory(pool)
    assert len(run.llm.calls) == 36
    assert len(run.report.selection.winners) == 2


def test_adaptive_stop_counts_one_event_instead_of_many_qualified_copies(factory):
    pool = [article(f"copy-{i:03}", "UAE approves national industrial emissions regulation") for i in range(36)]
    run = factory(pool)
    assert len(run.llm.calls) == 36
    assert len(run.report.selection.winners) == 1


@pytest.mark.parametrize("title,snippet,score,story_type,is_new", [
    ("Regional pomegranate festival reports sixty tonnes in sales", "Routine fair sales report.", 3, "routine_event", False),
    ("Farmers celebrate the start of the harvest season", "Seasonal harvest ceremony and tourism description.", 3, "routine_event", False),
    ("Poultry farm receives first free-range product label", "A product label is awarded; no capacity change is reported.", 3, "routine_event", False),
    ("Relief agency delivers food baskets to displaced families", "The report gives the number of baskets delivered locally.", 3, "humanitarian_relief", True),
    ("Government approves livestock production financing", "Funding will finance livestock production and increase domestic capacity.", 4, "investment_financing", True),
    ("UN reports halted food supplies and worsening malnutrition", "Primary report: commercial supply stoppage across the territory and its material food-availability consequence.", 4, "supply_disruption", True),
    ("Fertilizer disruption cuts projected regional harvests", "Confirmed fertilizer shortages will reduce agricultural output across several countries.", 4, "supply_disruption", True),
    ("UAE updates strategy to expand domestic food production", "The new national strategy sets a measurable domestic-production target.", 4, "policy_regulation", True),
    ("Agricultural fair announces financing for new cold storage", "Signed financing will add 20000 tonnes of cold storage and serve regional growers.", 4, "investment_financing", True),
    ("Certified poultry producer commissions new processing line", "The commercial line adds 30000 tonnes in annual capacity.", 4, "infrastructure_project", True),
])
def test_editorial_distinctions_reach_real_prompt_parser_and_unchanged_gate(factory, title, snippet, score, story_type, is_new):
    captured = []

    def create(**payload):
        captured.append(payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(dict(
            summary=snippet, why_it_matters=snippet, relevance_score=score,
            editorial_significance=3, region=["UAE"],
            story_type=story_type, is_new_development=is_new,
        ))))])

    llm = LlmClient.__new__(LlmClient)
    llm.model = "gpt-6-luna"
    llm.prompt_directory = Settings().prompt_directory
    llm.company_topics = Settings().discovery_topics
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    item = article("rubric", title)
    item.snippet = snippet
    run = factory([item], llm=llm, classify=lambda _: ("Relevant", 4, "UAE"))
    prompt = captured[0]["messages"][-1]["content"]
    assert "Routine/local activity generally scores at most 3" in prompt
    assert "Primary humanitarian relief and routine events are excluded" in prompt
    assert "Government financing of agricultural/livestock/fisheries production" in prompt
    assert run.report.evaluation.results[0].eligible == (score >= 4)
    assert bool(run.report.selection.winners) == (score >= 4)
    assert run.report.evaluation.results[0].required_relevance_score == 4


def audit_candidates():
    return [CandidateResult(
        Article(title=r["title"], url="", canonical_url=r["candidate_id"],
                source_name=r["publisher"], source_page_id=r["publisher"],
                publisher_key=r["publisher"], published_date=datetime.fromisoformat(r["published_date"])),
        EnrichedArticle("", "", r["relevance"], editorial_significance=r["editorial_significance"]),
        r["region"], queue_score=r["queue_score"], source_quality=r["source_quality"], required_relevance_score=4,
    ) for r in FIXTURE["qualified_candidates"]]


def test_actual_uae_strategy_pair_matches_without_inventing_audit_snippets():
    pair = [r for r in audit_candidates() if r.article.source_name in {"AGBI", "Fast Company Middle East"}]
    assert len(pair) == 2
    assert not probable_same_event(pair[0].article.title, pair[1].article.title)
    assert pair[0].article.snippet == pair[1].article.snippet == ""
    assert same_candidate_event(*pair)


def test_real_qualified_fixture_retains_strongest_policy_representative():
    result = select_final_candidates(
        audit_candidates(), weekly_state=WeeklyQueueState(),
        targets=Settings().weekly_region_targets, run_limit=12, publisher_cap=2, allow_regional_overflow=True,
    )
    assert len(result.winners) == 7  # Original eight, minus the UAE policy duplicate.
    assert result.rejected_by_constraint["same event"] == 2  # Gaza plus the UAE policy.
    assert "AGBI" in {r.article.source_name for r in result.winners}
    assert "Fast Company Middle East" not in {r.article.source_name for r in result.winners}


def test_metadata_overlap_recognizes_differently_worded_policy_announcement():
    a = candidate("alpha", "UAE", title="UAE government approves new industrial emissions policy")
    b = candidate("bravo", "UAE", title="Emissions regulation approval announced by UAE minister")
    snippet = "The government approved a binding industrial emissions policy covering factories with phased compliance deadlines and a national monitoring programme."
    a.article.snippet = b.article.snippet = snippet
    assert not probable_same_event(a.article.title, b.article.title)
    assert same_candidate_event(a, b)


@pytest.mark.parametrize("left,right", [
    ("ACWA signs agreement for 500 MW solar project in Iraq", "ACWA signs agreement for 500 MW solar project in Qatar"),
    ("ACWA signs agreement for 500 MW Basra solar project in Iraq", "ACWA signs agreement for 900 MW Najaf solar project in Iraq"),
    ("Failure to activate Hormuz fertilizer plan could trigger food crisis, UN official says", "Hormuz shipping disruption is starting to hit harvests, UN agency says"),
    ("UAE updates national food production strategy with 50% target for 2051", "UAE updates national food production strategy with 60% target for 2051"),
])
def test_related_developments_and_distinct_projects_are_not_merged(left, right):
    assert not same_candidate_event(candidate("alpha", title=left), candidate("bravo", title=right))


def test_fuzzy_policy_match_requires_publication_proximity():
    pair = [r for r in audit_candidates() if r.article.source_name in {"AGBI", "Fast Company Middle East"}]
    pair[1].article.published_date += timedelta(days=10)
    assert not same_candidate_event(*pair)


def test_exact_canonical_url_dedupe_precedes_conflicting_metadata():
    a = candidate("alpha", title="ACWA approves 500 MW project in Iraq")
    b = candidate("bravo", title="ACWA approves 900 MW project in Qatar")
    b.article.canonical_url = a.article.canonical_url
    assert same_candidate_event(a, b)


def test_equivalent_capacity_units_do_not_create_a_conflict():
    a = candidate("alpha", title="ACWA approves construction contract for 2 GW solar project at Basra in Iraq")
    b = candidate("bravo", title="ACWA approves construction contract for 2000 MW solar project at Basra in Iraq")
    assert probable_same_event(a.article.title, b.article.title)
    assert same_candidate_event(a, b)

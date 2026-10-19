"""Offline contracts for coverage initially and global quality during backfill."""

from collections import Counter
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from research_automation.clients.llm_client import LlmClient
from research_automation.config import Settings
from research_automation.models.candidate import CandidateResult
from research_automation.models.classification import ArticleClassification
from research_automation.pipeline.luna_selection import _allocate
from test_ingestion import NOW, _settings
from test_luna_selection import Enricher, article, factory


def classified(key, region, *, decision="Relevant", score=5, publisher=None, quality=8, age=0, phase="rss"):
    item = article(key, publisher=publisher, quality=quality)
    item.published_date = NOW - timedelta(hours=age)
    result = CandidateResult(item, None, region, source_quality=quality, phase=phase)
    result.classification = ArticleClassification(key, score, region, "Water Security", decision, "Synthetic metadata case.")
    return result


def test_initial_coverage_and_backfill_quality_have_distinct_priorities():
    strong = classified("strong", "Global")
    weak = classified("weak", "KSA", decision="Borderline", score=3)
    deficits = {"Global": 0, "KSA": 3}
    initial = _allocate([strong, weak], deficits, 8)
    backfill = _allocate([weak, strong], deficits, 8, quality_backfill=True, publishers={"strong": 20})
    assert initial[0] is weak  # Initial opportunity for the deficient country.
    assert backfill[0] is strong  # Neither shortage nor diversity overrides the editorial tier.


def test_next_eight_use_merged_regions_and_phases_not_the_shortest_region():
    strong = [classified(f"strong-{i}", region, phase=phase) for i, (region, phase) in enumerate([
        ("Global", "rss"), ("UAE", "expansion"), ("Egypt", "rss"), ("Global", "expansion"),
        ("Egypt", "expansion"), ("UAE", "rss"), ("Global", "rss"), ("Global", "expansion"),
    ])]
    weak = [classified(f"weak-{i}", "KSA", decision="Borderline", score=3) for i in range(8)]
    pool = [*weak, *reversed(strong)]
    ordered = _allocate(pool, {"KSA": 3}, 8, quality_backfill=True)
    assert {id(item) for item in ordered[:8]} == {id(item) for item in strong}
    assert {item.phase for item in ordered[:8]} == {"rss", "expansion"}


def test_backfill_diversifies_sources_within_equal_editorial_tiers():
    best = classified("best", "Global", publisher="same", quality=10)
    repeat = classified("repeat", "Global", publisher="same", quality=9)
    other = classified("other", "Egypt", publisher="other", quality=8)
    ordered = _allocate([repeat, other, best], {"KSA": 3}, 8, quality_backfill=True)
    assert ordered[:3] == [best, other, repeat]
    next_batch = _allocate([repeat, other], {"KSA": 3}, 8, quality_backfill=True, publishers={"same": 2})
    assert next_batch[0] is other


def test_shortage_only_breaks_ties_after_quality_and_recency():
    best = classified("best", "Global", quality=9)
    weak = classified("weak", "KSA", quality=8)
    assert _allocate([weak, best], {"KSA": 3}, 8, quality_backfill=True)[0] is best
    fresh = classified("fresh", "Global", quality=8)
    old = classified("old", "KSA", quality=8, age=1)
    assert _allocate([old, fresh], {"KSA": 3}, 8, quality_backfill=True)[0] is fresh
    tied = classified("tied", "KSA", quality=8)
    assert _allocate([fresh, tied], {"KSA": 3}, 8, quality_backfill=True)[0] is tied


def test_real_orchestrator_switches_after_32_and_never_repeats_or_exceeds_48(factory, tmp_path):
    pool = [article(f"{region}-{i:03}") for region in ("Global", "UAE", "KSA", "Egypt") for i in range(30)]

    def classification(metadata):
        region = metadata["publisher"].split("-")[0]
        return ("Relevant", 5, region) if region == "Global" else ("Borderline", 3, region)

    settings = replace(
        _settings(tmp_path / "state"), article_selection_mode="luna",
        article_queue_weekly_target_global=3, article_queue_weekly_target_uae=4,
        article_queue_weekly_target_ksa=3, article_queue_weekly_target_egypt=2,
    )
    run = factory(pool, settings=settings, classify=classification, llm=Enricher(score=3))
    assert len(run.llm.calls) == 48
    assert len({title for title, _ in run.llm.calls}) == 48
    assert set(region[0] for _, region in run.llm.calls[:32]) == {"Global", "UAE", "KSA", "Egypt"}
    assert Counter(region[0] for _, region in run.llm.calls[32:40]) == {"Global": 8}
    assert Counter(region[0] for _, region in run.llm.calls[40:48]) == {"Global": 8}
    assert run.report.enrichment_budget == {"initial": 32, "maximum": 48, "backfill_batch": 8, "attempted": 48}
    assert run.notion.creates == run.notion.updates == []
    assert not run.settings.seen_articles_path.exists()


@pytest.mark.parametrize("title,snippet,relevance,significance,qualifies", [
    ("Government finances livestock production", "Funding for livestock production is approved; allocation and outcomes are unspecified.", 4, 2, True),
    ("Agricultural-production programme receives SAR1.2bn support", "SAR1.2bn in support for agricultural production is confirmed; timeframe and implementation details are absent.", 4, 3, True),
    ("Egypt commits investment to water infrastructure", "A water-infrastructure investment is approved; capacity and expected impact are not stated.", 4, 2, True),
    ("Issuer launches a green bond", "No mission-linked use of proceeds is supplied.", 3, 3, False),
    ("Company publishes sustainability ambitions", "The statement gives no concrete mission-linked development.", 2, 2, False),
])
def test_missing_scale_reduces_significance_not_supported_mission_fit(factory, title, snippet, relevance, significance, qualifies):
    # Synthetic evidence and fixed outputs verify prompt delivery/parser/gate,
    # not the real model's judgment or unavailable snippets from the audit.
    requests = []

    def create(**arguments):
        requests.append(arguments)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(dict(
            summary=snippet, why_it_matters=snippet, relevance_score=relevance,
            editorial_significance=significance, region=["Egypt"],
            story_type="investment_financing", is_new_development=True,
        ))))])

    llm = LlmClient.__new__(LlmClient)
    llm.model = "gpt-6-luna"
    llm.prompt_directory = Settings().prompt_directory
    llm.company_topics = Settings().discovery_topics
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    item = article("rubric", title)
    item.snippet = snippet
    run = factory([item], llm=llm, classify=lambda _: ("Relevant", 4, "Egypt"))
    prompt = requests[0]["messages"][-1]["content"]
    assert "Do not reduce relevance merely because scale, timeframe, implementation details," in prompt
    assert "Reflect those\nevidence or scale limitations in editorial significance instead" in prompt
    assert "green bond without stated mission-linked use of proceeds may remain relevance" in prompt
    result, = run.report.evaluation.results
    assert result.eligible is qualifies  # The strict relevance threshold is unchanged.
    assert bool(run.report.selection.winners) == (qualifies or (relevance >= 3 and significance >= 3))
    if run.report.selection.winners:
        assert run.report.selection.winners[0].selection_tier == ("strict" if qualifies else "fallback")
    assert result.enrichment.relevance_score == relevance
    assert result.enrichment.editorial_significance == significance
    assert result.required_relevance_score == 4


@pytest.mark.parametrize("title,snippet,decision,score", [
    ("Agency distributes hundreds of food baskets", "An isolated delivery of several hundred baskets is reported.", "Irrelevant", 1),
    ("Food aid programme expands across the region", "A major funded programme expansion adds permanent distribution capacity.", "Relevant", 4),
    ("Food supply programme changes", "Sparse metadata may describe a structural supply change; details are absent.", "Borderline", 3),
])
def test_primary_relief_is_excluded_but_sector_developments_preserve_recall(factory, title, snippet, decision, score):
    item = article("aid", title)
    item.snippet = snippet
    run = factory([item], classify=lambda _: (decision, score, "Global"))
    prompt = run.requests[0]["messages"][0]["content"]
    assert "when its primary news is the humanitarian/conflict situation" in prompt
    assert "Structural food/water" in prompt
    assert "Sparse but credible consequence -> Borderline" in prompt
    result, = run.report.evaluation.results
    assert result.classification.decision == decision
    assert result.classification.relevance_score == score
    assert result.enrichment_attempted is (decision != "Irrelevant")
    assert len(run.llm.calls) == int(decision != "Irrelevant")

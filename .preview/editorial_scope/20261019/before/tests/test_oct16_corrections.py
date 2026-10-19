from datetime import datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.pipeline import candidate_ranking as ranking
from research_automation.pipeline.article_retrieval import ArticleRetrievalResult
from research_automation.pipeline.candidate_audit import build_candidate_audit, write_candidate_audit
from research_automation.pipeline.selection import WeeklyQueueState, select_final_candidates


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "oct16_corrections.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["now"])
SETTINGS = Settings()


def article(key, title="UAE expands water treatment plant", *, snippet=None, region="UAE", discovery=False, registered=True, quality=8):
    return Article(
        title=title, snippet=snippet or title, url=f"https://{key}.example/story", canonical_url=f"https://{key}.example/story",
        source_name=key, source_page_id=key if registered else "", region=[region],
        published_date=NOW - timedelta(hours=1), publisher_key=key,
        source_editorial_quality=quality if registered else None,
        discovery_provider="offline provider" if discovery else None,
    )


def frozen_article(row):
    a = article(row["key"], row["title"], snippet=row["snippet"], registered=row["registered"], discovery=row["discovery"], quality=row["quality"])
    a.url = a.canonical_url = row["url"]
    a.source_name = row["publisher"]
    a.region = list(row["source_regions"])
    a.published_date = datetime.fromisoformat(row["published"])
    return a


def prepare(a):
    return ranking._prepare_candidate(a, settings=SETTINGS, now=NOW)


def enriched(score=4):
    return EnrichedArticle("offline summary", "offline mission connection", score,
                           editorial_significance=3, significance_reason="Supported infrastructure capacity change.")


def evaluate(pool, **kwargs):
    return ranking.evaluate_candidate_pool(pool, deficits={"Global": 3, "UAE": 4, "KSA": 3, "Egypt": 2},
                                           settings=SETTINGS, now=NOW, **kwargs)


def test_frozen_false_positives_are_rejected_before_enrichment():
    keys = {"negation", "battery_definition", "battery_science", "crypto", "flights"}
    rows = [row for row in FIXTURE["candidates"] if row["key"] in keys]
    assert len(rows) == 5 and all(row["before"]["reason"] == "" for row in rows)
    result = evaluate([frozen_article(row) for row in rows], enrich=lambda _: pytest.fail("off-mission metadata must not spend a model request"))
    assert len(result.results) == 5
    assert all(r.rejection_reason and not r.enrichment_attempted for r in result.results)
    assert result.shortlisted_counts == {}


def test_frozen_false_negatives_gain_direct_mission_signals():
    for row in FIXTURE["candidates"]:
        if row["key"] in {"veal", "gerd", "harvests"}:
            r = prepare(frozen_article(row))
            assert not row["before"]["direct"]
            assert r.direct_mission_signals and not r.rejection_reason
    harvest = next(row for row in FIXTURE["candidates"] if row["key"] == "harvests")
    assert prepare(frozen_article(harvest)).target_region == "Global"


def test_frozen_geography_and_commission_corrections():
    rows = {row["key"]: row for row in FIXTURE["candidates"]}
    for key, location in (("iraq", "Iraq"), ("libya", "Libya"), ("qatar", "Qatar")):
        r = prepare(frozen_article(rows[key]))
        assert r.target_region == "Global" and not r.rejection_reason
        assert location in r.region_assignment_basis
    assert rows["iraq"]["before"]["region"] == rows["libya"]["before"]["region"] == "KSA"
    assert rows["qatar"]["before"]["reason"] == "no exact target region"
    r = prepare(frozen_article(rows["commission"]))
    assert rows["commission"]["before"]["concrete"]
    assert not r.concrete_development and r.direct_mission_signals and not r.rejection_reason
    r = prepare(frozen_article(rows["self_newsletter"]))
    assert "self-published" in r.rejection_reason and r.target_region is None


@pytest.mark.parametrize("title", [
    "UAE leader says neither water nor energy is the currency of trust",
    "Dubai grants cryptocurrency trading platform a regulatory licence",
    "Passenger flights cancelled at Dubai airport after disruption",
    "Molecular clustering in lithium battery electrolytes",
    "Anode interfaces improve lithium batteries in laboratory research",
])
def test_generalized_off_mission_examples(title):
    assert prepare(article("negative", title)).rejection_reason


@pytest.mark.parametrize("title,snippet", [
    ("UAE water treatment plant is not yet operational", "The plant will add water reuse capacity."),
    ("Not only water reuse: UAE expands irrigation programme", "New irrigation infrastructure supports farms."),
    ("UAE crypto miners sign solar power agreement", "The agreement supplies renewable electricity to mining operations."),
    ("Dubai flight disruption delays fertilizer deliveries", "The shipping disruption directly threatens food security."),
    ("Battery electrolytes advance grid storage deployment in Saudi Arabia", "The pilot tests utility-scale energy storage."),
    ("Egypt approves battery manufacturing project", "The facility adds annual assembly capacity."),
    ("Oman funds livestock and veal production", "The agricultural programme expands regional supply."),
    ("Egypt and Ethiopia resume talks over Nile basin dam dispute", "The negotiations concern the Nile dam."),
    ("Shipping delays threaten regional harvests", "Hormuz disruption threatens harvests and fertilizer supplies."),
])
def test_legitimate_mission_bridges_remain_eligible(title, snippet):
    assert prepare(article("positive", title, snippet=snippet, region="Global")).rejection_reason == ""


def test_medical_gerd_is_not_a_water_signal_and_commissioning_is_still_concrete():
    assert prepare(article("medical", "Egypt clinic researches GERD treatment")).direct_mission_signals == []
    r = prepare(article("commissioned", "Saudi Arabia commissions new water treatment plant"))
    assert r.concrete_development and not r.rejection_reason


@pytest.mark.parametrize("title,snippet,source,expected", [
    ("Iraq in talks with Saudi ACWA to increase solar capacity", "A solar project would be built in Iraq.", "KSA", "Global"),
    ("UAE developer builds solar facility in Egypt", "The Egyptian project is under construction.", "UAE", "Egypt"),
    ("Egypt awards desalination project to UAE company", "A UAE partner will construct the Egyptian facility.", "UAE", "Egypt"),
    ("Qatar expands renewable energy capacity", "The new generation assets will be in Qatar.", "UAE", "Global"),
    ("Libya floods damage water infrastructure", "Flooding disrupted services in Libya.", "KSA", "Global"),
    ("Saudi firm builds municipal water plant in India", "An Indian city is the site of the project.", "KSA", None),
    ("Egypt approves fertilizer manufacturing facility", "The facility will contribute to global fertilizer supply.", "Global", "Egypt"),
    ("UN report: global grain prices rise after China export restrictions", "Global food security is affected.", "KSA", "Global"),
])
def test_event_location_nationality_and_global_scope(title, snippet, source, expected):
    r = prepare(article("geography", title, snippet=snippet, region=source))
    assert r.target_region == expected
    assert bool(r.rejection_reason) == (expected is None)


def test_discovery_query_region_cannot_establish_article_geography():
    a = article("newsletter", "Independent newsletter about water security", discovery=True, region="Egypt")
    r = prepare(a)
    assert r.target_region is None and r.rejection_reason == "no exact target region"
    assert r.source_region_hints == ["Egypt"]


@pytest.mark.parametrize("host,excluded", [
    ("somamater.com", True), ("www.somamater.com", True), ("news.somamater.com", True),
    ("notsomamater.com", False), ("somamater.com.example", False), ("independent.example", False),
])
def test_self_publisher_exclusion_is_domain_bounded(host, excluded):
    a = article("self", "Egypt launches new water treatment project", discovery=True)
    a.url = a.canonical_url = f"https://{host}/newsletters/edition"
    assert ("self-published" in prepare(a).rejection_reason) == excluded


@pytest.mark.parametrize("duplicate_of", ["previous_phase", "excluded_cache"])
def test_resolved_duplicate_backfills_without_losing_discovery_or_budget(duplicate_of):
    calls = []
    attempted = set()
    first = evaluate([article(f"rss{i}") for i in range(6)],
                     enrich=lambda a: calls.append(a.publisher_key) or enriched(2),
                     attempted_urls=attempted, phase_ceiling_per_region=6)
    assert first.shortlisted_counts == {"UAE": 6}
    duplicate = article("duplicate", discovery=True, quality=10)
    valid = [article(f"discovery{i}", discovery=True) for i in range(3)]
    duplicate_url = "https://rss0.example/story" if duplicate_of == "previous_phase" else "https://cached.example/story"
    excluded = {duplicate_url} if duplicate_of == "excluded_cache" else set()
    def retrieve(a):
        canonical = duplicate_url if a is duplicate else a.canonical_url
        return ArticleRetrievalResult(canonical, "resolved_redirect", "extracted", "PRIVATE BODY")
    second = evaluate([article("better-rss", quality=10), duplicate, *valid],
                      enrich=lambda a: calls.append(a.publisher_key) or enriched(), retrieve=retrieve,
                      attempted_urls=attempted, excluded_urls=excluded, already_shortlisted=first.shortlisted_counts,
                      reserve_discovery=True, phase="expansion", stop_when_qualified=False)
    assert len(calls) == len(set(calls)) == 8
    assert second.shortlisted_counts == {"UAE": 2}
    assert all(key.startswith("discovery") for key in calls[-2:])
    rejected = next(r for r in second.results if r.article is duplicate)
    assert rejected.rejection_reason == "duplicate URL"
    assert not rejected.shortlisted and not rejected.enrichment_attempted
    assert any(r.rejection_reason == "shortlist ceiling" for r in second.results)


def test_duplicates_cannot_make_the_backfill_loop_unbounded():
    calls = []
    pool = [article(f"alias{i}", discovery=True) for i in range(15)]
    result = evaluate(pool, enrich=lambda a: calls.append(a) or enriched(),
                      retrieve=lambda _: ArticleRetrievalResult("https://cached.example/story", "resolved_redirect", "extracted"),
                      excluded_urls={"https://cached.example/story"}, reserve_discovery=True)
    assert calls == [] and len(result.results) == len(pool)
    assert result.shortlisted_counts == {}


def test_same_phase_canonical_alias_is_backfilled_without_duplicate_enrichment():
    calls = []
    pool = [article(key, discovery=True) for key in ("a-first", "b-alias", "c-replacement")]
    def retrieve(a):
        canonical = "https://publisher.example/shared" if a.publisher_key != "c-replacement" else a.canonical_url
        return ArticleRetrievalResult(canonical, "resolved_redirect", "extracted")
    result = evaluate(pool, enrich=lambda a: calls.append(a.canonical_url) or enriched(), retrieve=retrieve,
                      already_shortlisted={"UAE": 6}, reserve_discovery=True, stop_when_qualified=False)
    assert len(calls) == len(set(calls)) == 2
    assert result.shortlisted_counts == {"UAE": 2}
    assert sum(r.rejection_reason == "duplicate URL" for r in result.results) == 1


def test_self_publisher_redirect_is_skipped_and_backfilled():
    calls = []
    alias = article("alias", discovery=True, quality=10)
    valid = article("replacement", discovery=True)
    def retrieve(a):
        canonical = "https://somamater.com/previous-edition" if a is alias else a.canonical_url
        return ArticleRetrievalResult(canonical, "resolved_redirect", "extracted")
    result = evaluate([alias, valid], enrich=lambda a: calls.append(a) or enriched(), retrieve=retrieve,
                      already_shortlisted={"UAE": 7}, reserve_discovery=True, stop_when_qualified=False)
    assert calls == [valid] and result.shortlisted_counts == {"UAE": 1}
    rejected = next(r for r in result.results if r.article is alias)
    assert "self-published" in rejected.rejection_reason and not rejected.enrichment_attempted


def test_audit_explains_stages_evidence_rationale_and_unchanged_gates(tmp_path):
    duplicate = article("duplicate")
    pool = [article("metadata", "UAE celebrity signs an autograph"),
            article("geography", "Chennai municipal water project advances", region="KSA"), duplicate,
            article("low"), article("unknown", registered=False), article("winner")]
    scores = {"low": 3, "unknown": 4, "winner": 4}
    def retrieve(a):
        canonical = "https://cached.example/story" if a is duplicate else a.canonical_url
        return ArticleRetrievalResult(canonical, "resolved_redirect", "extracted", "PRIVATE FULL BODY")
    result = evaluate(pool, enrich=lambda a: enriched(scores[a.publisher_key]), retrieve=retrieve,
                      excluded_urls={"https://cached.example/story"})
    selection = select_final_candidates([r for r in result.results if r.eligible], weekly_state=WeeklyQueueState(),
                                        targets=SETTINGS.weekly_region_targets, run_limit=12, publisher_cap=2)
    report = SimpleNamespace(evaluation=result, selection=selection, dry_run=True)
    audit = build_candidate_audit(report)
    by_key = {row["publisher"]: row for row in audit["candidates"]}
    assert by_key["metadata"]["decision_stage"] == "metadata_rejection"
    assert by_key["geography"]["decision_stage"] == "geography_routing_rejection"
    assert by_key["duplicate"]["decision_stage"] == "duplicate_before_enrichment"
    assert by_key["low"]["decision_stage"] == "llm_relevance_rejection"
    assert by_key["unknown"]["decision_stage"] == "unregistered_publisher_threshold_rejection"
    assert by_key["winner"]["decision_stage"] == "final_selection"
    assert by_key["winner"]["evidence_retrieval_status"] == "extracted"
    assert by_key["winner"]["significance_rationale"] == "Supported infrastructure capacity change."
    assert "actual_llm_enrichment" in by_key["low"]["stages"]
    assert by_key["unknown"]["required_relevance_score"] == 5
    assert by_key["winner"]["required_relevance_score"] == 4
    assert sum(row["enrichment_attempted"] for row in audit["candidates"]) == 3
    assert len(selection.winners) == 1
    path = write_candidate_audit(report, tmp_path, NOW)
    data = path.read_text(encoding="utf-8") + path.with_suffix(".json").read_text(encoding="utf-8")
    assert "PRIVATE FULL BODY" not in data
    assert "unregistered_publisher_threshold_rejection" in data
    assert "Supported infrastructure capacity change." in data
    assert SETTINGS.article_shortlist_max_per_region == 8
    assert SETTINGS.max_articles_per_publisher_per_week == 2
    assert SETTINGS.weekly_region_targets == {"Global": 3, "UAE": 4, "KSA": 3, "Egypt": 2}
    assert ranking.calculate_queue_score(4, 8, 3) == 76

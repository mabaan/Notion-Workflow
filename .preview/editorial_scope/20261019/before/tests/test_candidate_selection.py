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
from research_automation.pipeline.ingestion import _merge_evaluations
from research_automation.pipeline.relevance import matched_direct_mission_signals
from research_automation.pipeline.selection import WeeklyQueueState, select_final_candidates
from research_automation.utils.hashing import build_url_hash


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "candidate_selection.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["now"])
SETTINGS = Settings()


def article(key, title="Global water company issues routine announcement", *, region="Global", quality=8, age=0, registered=True, snippet=None, discovery=False):
    return Article(
        title=title, url=f"https://{key}.example/story", canonical_url=f"https://{key}.example/story",
        source_name=key, source_page_id=key if registered else "",
        published_date=NOW - timedelta(hours=age), snippet=snippet or title,
        region=[region], source_editorial_quality=quality if registered else None,
        publisher_key=key, discovery_provider="Brave Search Fallback" if discovery else None,
    )


def enriched(score=5):
    return EnrichedArticle("offline summary", "offline mission connection", score, editorial_significance=4)


def evaluate(pool, **kwargs):
    return ranking.evaluate_candidate_pool(pool, deficits={"Global": 3, "UAE": 4, "KSA": 3, "Egypt": 2}, settings=SETTINGS, now=NOW, **kwargs)


def regressions():
    result = {}
    for row in FIXTURE["regressions"]:
        a = article(row["key"], row["title"], quality=row["quality"], snippet=row["snippet"])
        a.source_name = row["publisher"]
        a.region = list(row["regions"])
        a.published_date = datetime.fromisoformat(row["published"])
        result[row["key"]] = a
    return result


def test_regression_geography_and_mission_ordering():
    cases = regressions()
    prepared = {key: ranking._prepare_candidate(a, settings=SETTINGS, now=NOW) for key, a in cases.items()}
    assert prepared["istanbul"].rejection_reason == "outside geographic mandate"
    assert prepared["istanbul"].target_region is None
    assert "fallback blocked" in prepared["istanbul"].region_assignment_basis
    assert prepared["hormuz"].target_region == "Global"
    assert prepared["hormuz"].rejection_reason == ""
    assert prepared["bahrain"].target_region == "Global"
    assert "energy transition" in prepared["bahrain"].direct_mission_signals
    assert prepared["bahrain"].rejection_reason == ""
    ordered = ranking._source_diverse_shortlist([prepared["routine"], prepared["desalination"]])
    assert ordered[0].article is cases["desalination"]


@pytest.mark.parametrize("singular,plural", [("grid", "grids"), ("battery", "batteries"), ("crop", "crops"), ("farm", "farms"), ("fertilizer", "fertilisers")])
def test_common_mission_variants(singular, plural):
    left = matched_direct_mission_signals(article("a", f"New {singular} project announced"), SETTINGS.discovery_topics)
    right = matched_direct_mission_signals(article("b", f"New {plural} project announced"), SETTINGS.discovery_topics)
    assert left and left == right


def test_global_scope_is_not_a_generic_global_word_or_foreign_publisher():
    local = article("local", "Global company upgrades Chennai municipal water plant", region="KSA")
    systemic = article("systemic", "UN report: global grain prices rise after China export restrictions")
    results = evaluate([local, systemic], enrich=lambda _: enriched())
    assert next(r for r in results.results if r.article is local).rejection_reason == "outside geographic mandate"
    assert next(r for r in results.results if r.article is systemic).eligible


def test_global_language_in_local_project_description_does_not_override_geography():
    a = article("local", "Chennai municipal water plant gets funding", region="KSA",
                snippet="Promoters say the local grant advances global water security.")
    result = evaluate([a], enrich=lambda _: enriched())
    assert result.results[0].rejection_reason == "outside geographic mandate"


def test_waterfront_and_unrelated_carbon_prefix_do_not_supply_mission_evidence():
    a = article("restaurant", "UAE waterfront restaurant launches carbonara menu at 999 locations")
    assert matched_direct_mission_signals(a, SETTINGS.discovery_topics) == []


def test_multi_region_uses_title_before_description_and_has_no_uae_tie_priority():
    central = article("central", "Saudi Arabia approves new desalination plant", region="Global", snippet="A UAE contractor will construct the Saudi water project.")
    tied = article("tied", "Saudi Arabia and UAE agree water research programme", region="Global")
    dominant = article("dominant", "Saudi Arabia expands Riyadh water project with UAE partner", region="Global")
    assert ranking._prepare_candidate(central, settings=SETTINGS, now=NOW).target_region == "KSA"
    assert ranking._prepare_candidate(dominant, settings=SETTINGS, now=NOW).target_region == "KSA"
    assert ranking._prepare_candidate(tied, settings=SETTINGS, now=NOW).target_region is None


def test_domestic_project_is_not_reassigned_by_global_description():
    a = article("egypt", "Egypt approves fertilizer manufacturing facility", region="Global",
                snippet="The facility would contribute to global fertilizer supply.")
    assert ranking._prepare_candidate(a, settings=SETTINGS, now=NOW).target_region == "Egypt"


def test_foreign_mission_project_with_explicit_mena_bridge_is_not_publisher_only():
    a = article("bridge", "China signs solar manufacturing agreement", region="KSA",
                snippet="The agreement will build a solar manufacturing plant in Egypt.")
    r = ranking._prepare_candidate(a, settings=SETTINGS, now=NOW)
    assert r.rejection_reason == ""
    assert r.target_region == "Egypt"


def test_quality_and_concrete_development_precede_minutes_and_numeric_noise():
    good = article("good", "Global water treatment plant agreement approved", age=1)
    weak = article("weak", "Global water treatment company lists 999999 awards", age=0)
    prepared = [ranking._prepare_candidate(a, settings=SETTINGS, now=NOW) for a in (weak, good)]
    assert ranking._source_diverse_shortlist(prepared)[0].article is good
    weak.source_editorial_quality = 10
    good.source_editorial_quality = 2
    prepared = [ranking._prepare_candidate(a, settings=SETTINGS, now=NOW) for a in (good, weak)]
    assert ranking._source_diverse_shortlist(prepared)[0].article is weak


def test_publisher_diversity_survives_new_order():
    pool = [article(f"a{i}", "Global desalination project approved") for i in range(3)]
    for a in pool:
        a.publisher_key = "same-publisher"
    other = article("other", quality=2)
    prepared = [ranking._prepare_candidate(a, settings=SETTINGS, now=NOW) for a in [*pool, other]]
    ordered = ranking._source_diverse_shortlist(prepared)
    assert [r.article.publisher_key for r in ordered[:2]] == ["same-publisher", "other"]


@pytest.mark.parametrize("suitable_discovery,expected_discovery", [(0, 0), (1, 1), (3, 2)])
def test_bounded_discovery_reservation_and_rss_backfill(suitable_discovery, expected_discovery):
    pool = [article(f"rss{i}") for i in range(4)]
    pool += [article(f"discovery{i}", "Global water security supply agreement", age=48, registered=False, discovery=True) for i in range(suitable_discovery)]
    pool.append(article("invalid-discovery", "Local celebrity wins award", discovery=True))
    calls = []
    result = evaluate(pool, already_shortlisted={"Global": 6}, reserve_discovery=True, stop_when_qualified=False,
                      enrich=lambda a: calls.append(a) or enriched())
    assert result.shortlisted_counts == {"Global": 2}
    assert len(calls) == 2
    assert sum(bool(a.discovery_provider) for a in calls) == expected_discovery
    assert len({a.canonical_url for a in calls}) == 2


def test_no_repeat_enrichment_after_canonical_resolution_across_phases():
    attempted = set()
    first = article("first")
    alias = article("alias", "Global water security supply agreement", discovery=True)
    canonical = "https://publisher.example/canonical"
    calls = []
    retrieve = lambda _: ArticleRetrievalResult(canonical, "resolved_redirect", "extracted", "evidence")
    phase1 = evaluate([first], enrich=lambda a: calls.append(a) or enriched(), retrieve=retrieve, attempted_urls=attempted)
    phase2 = evaluate([alias], enrich=lambda a: calls.append(a) or enriched(), retrieve=retrieve,
                      attempted_urls=attempted, already_shortlisted=phase1.shortlisted_counts, phase="expansion", reserve_discovery=True)
    assert len(calls) == 1
    assert phase2.results[0].rejection_reason == "duplicate URL"
    assert alias.url_hash == build_url_hash(canonical)
    assert alias.url == "https://alias.example/story"


def test_failed_enrichment_is_not_retried_in_expansion():
    attempted = set()
    calls = []
    a = article("failure")
    def fail(a):
        calls.append(a)
        raise RuntimeError("provider failure")
    evaluate([a], enrich=fail, attempted_urls=attempted)
    second = evaluate([a], enrich=fail, attempted_urls=attempted, phase="expansion")
    assert len(calls) == 1
    assert second.results[0].rejection_reason == "duplicate URL"


def run_comparison(*, legacy, monkeypatch):
    specification = FIXTURE["comparison"]
    rss = [article(f"routine{i}", age=i) for i in range(specification["routine_count"])]
    scores = {a.publisher_key: 2 for a in rss}
    for row in specification["rss"]:
        rss.append(article(row["key"], row["title"], age=row["age_hours"], snippet=row["snippet"]))
        scores[row["key"]] = row["mock_relevance"]
    row = specification["discovery"]
    discovered = article(row["key"], row["title"], age=row["age_hours"], snippet=row["snippet"], discovery=True, registered=False)
    scores[row["key"]] = row["mock_relevance"]
    calls = []
    def enrich(a):
        calls.append(a.publisher_key)
        return enriched(scores[a.publisher_key])
    with monkeypatch.context() as patch:
        if legacy:
            # Frozen pre-change ordering, with the same mission tier and publisher diversity.
            patch.setattr(ranking, "_metadata_rank_sort", lambda r: (
                -r.article.published_date.timestamp(), -min(len(r.article.snippet.strip()), 500),
                -len(r.matched_topics), r.article.source_page_id == "", -(r.source_quality or 0), r.article.canonical_url,
            ))
        first = evaluate(rss, enrich=enrich, phase_ceiling_per_region=6)
        deferred = [r.article for r in first.results if r.rejection_reason == "shortlist deferred"]
        second = evaluate([*deferred, discovered], enrich=enrich, already_shortlisted=first.shortlisted_counts,
                          reserve_discovery=not legacy, phase="expansion", stop_when_qualified=False)
    merged = _merge_evaluations(first, second)
    selection = select_final_candidates([r for r in merged.results if r.eligible], weekly_state=WeeklyQueueState(),
                                        targets={"Global": 3}, run_limit=12, publisher_cap=2)
    return calls, SimpleNamespace(evaluation=merged, selection=selection, dry_run=True)


def test_frozen_old_new_comparison_with_fixed_scores(monkeypatch):
    old_calls, old_report = run_comparison(legacy=True, monkeypatch=monkeypatch)
    new_calls, new_report = run_comparison(legacy=False, monkeypatch=monkeypatch)
    assert len(old_calls) == len(new_calls) == 8
    assert old_report.selection.winners == []
    assert {w.article.publisher_key for w in new_report.selection.winners} == {
        "strong-desalination", "strong-battery", "discovered-fertilizer"
    }
    assert set(new_calls) - set(old_calls) == {"strong-desalination", "strong-battery", "discovered-fertilizer"}


def test_audit_tracks_phase_reconsideration_and_excludes_content(tmp_path, monkeypatch):
    _, report = run_comparison(legacy=False, monkeypatch=monkeypatch)
    for result in report.evaluation.results:
        result.article.article_text = "PRIVATE FULL BODY"
    audit = build_candidate_audit(report)
    assert audit["unique_input_candidates"] == 11
    assert audit["evaluation_records"] == 15
    assert audit["reconsidered_across_phases"] == 4
    assert sum(row["enrichment_attempted"] for row in audit["candidates"]) == 8
    assert sum(row["selected"] for row in audit["candidates"]) == 3
    assert sum(stage["shortlisted"] for stage in audit["counts_by_phase_and_region"]) == 8
    path = write_candidate_audit(report, tmp_path, NOW)
    contents = path.read_text(encoding="utf-8") + path.with_suffix(".json").read_text(encoding="utf-8")
    assert "PRIVATE FULL BODY" not in contents
    assert "metadata_rank" in contents and "region_assignment_basis" in contents
    assert "Relevance / significance" in contents
    assert json.loads(path.with_suffix(".json").read_text(encoding="utf-8")) == audit


def test_audit_omits_provider_error_details():
    def fail(_):
        raise RuntimeError("SECRET_API_CREDENTIAL")
    ev = evaluate([article("error")], enrich=fail)
    report = SimpleNamespace(evaluation=ev, selection=SimpleNamespace(winners=[], shortages={"Global": 3}), dry_run=True)
    assert "SECRET_API_CREDENTIAL" not in json.dumps(build_candidate_audit(report))


def test_audit_does_not_collapse_distinct_candidates_without_urls():
    pool = [article("one"), article("two")]
    for a in pool:
        a.url = a.canonical_url = ""
    ev = evaluate(pool, enrich=lambda _: pytest.fail("invalid URLs must not be enriched"))
    report = SimpleNamespace(evaluation=ev, selection=SimpleNamespace(winners=[], shortages={"Global": 3}), dry_run=True)
    audit = build_candidate_audit(report)
    assert audit["unique_input_candidates"] == 2
    assert audit["unique_canonical_urls"] == 0


def test_relevance_thresholds_and_freshness_unchanged():
    pool = [article("registered"), article("unregistered", registered=False), article("stale", age=8 * 24)]
    result = evaluate(pool, enrich=lambda _: enriched(4))
    by_key = {r.article.publisher_key: r for r in result.results}
    assert by_key["registered"].eligible
    assert by_key["unregistered"].rejection_reason == "relevance below 5"
    assert by_key["stale"].rejection_reason == "outside freshness window"
    assert SETTINGS.article_shortlist_initial_per_region == 6
    assert SETTINGS.article_shortlist_max_per_region == 8
    assert ranking.calculate_queue_score(5, 10, 5) == 100

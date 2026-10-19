"""Offline integration contracts; model judgment itself is not mocked as evidence."""

from dataclasses import replace
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace

import httpx
from openai import OpenAI
import pytest

from research_automation.clients.article_classifier import ArticleClassifier
from research_automation.clients.llm_client import LlmClient
from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.candidate import CandidateResult
from research_automation.pipeline import ingestion
from research_automation.pipeline.article_retrieval import ArticleRetrievalResult
from research_automation.pipeline.candidate_audit import build_candidate_audit
from research_automation.pipeline.candidate_ranking import _prepare_candidate, calculate_queue_score
from research_automation.pipeline.collect import CollectionResult
from research_automation.pipeline.ingestion import IngestionOptions, run_ingestion
from research_automation.pipeline.selection import WeeklyQueueState, select_final_candidates
from research_automation.utils.hashing import build_url_hash

from test_ingestion import FakeDiscovery, FakeNotion, NOW, _settings


BLUEBERRY = "Silal Group expands blueberry production in the UAE through partnership with IQ Berries - Zawya"
VEAL = "Egypt's minister approves new funding for National Veal Project - Zawya"


def article(key, title=None, *, hint="UAE", publisher=None, registered=True, quality=8):
    return Article(
        title=title or f"Concrete development involving sitekey{key}",
        url=f"https://publisher.example/{key}", canonical_url=f"https://publisher.example/{key}",
        source_name=publisher or key, source_page_id=(publisher or key) if registered else "",
        published_date=NOW, snippet="", region=[hint], source_editorial_quality=quality,
        publisher_key=publisher or key,
    )


class Enricher:
    def __init__(self, score=4, significance=3, region="Global", before=None):
        self.calls = []
        self.score = score
        self.significance = significance
        self.region = region
        self.before = before

    def enrich_article(self, candidate):
        if self.before:
            self.before()
        self.calls.append((candidate.title, list(candidate.region)))
        return EnrichedArticle(
            "Supported development", "Supported mission consequence", self.score,
            region=[self.region], editorial_significance=self.significance,
        )


@pytest.fixture
def factory(monkeypatch, tmp_path):
    monkeypatch.setattr(ingestion, "utc_now", lambda: NOW)
    clients = []

    def make(pool, *, classify=None, llm=None, settings=None, discovery_factory=FakeDiscovery,
             handler=None, notion=None, retrieve=None, options=None):
        settings = settings or replace(_settings(tmp_path / "state"), article_selection_mode="luna")
        requests = []

        def respond(request):
            payload = json.loads(request.content)
            requests.append(payload)
            metadata = json.loads(payload["messages"][1]["content"])["articles"]
            rows = []
            for item in reversed(metadata):
                decision, score, region = classify(item) if classify else ("Relevant", 4, "Global")
                rows.append(dict(
                    article_id=item["article_id"], decision=decision, relevance_score=score,
                    assigned_region=region, primary_mission_topic="Food Security",
                    justification="Supported mission development; final evidence assessment required.",
                    story_type="development", is_new_development=True,
                ))
            if handler:
                result = handler(payload, rows, len(requests))
                if isinstance(result, httpx.Response):
                    return result
                rows = result
            return httpx.Response(200, json=dict(
                id="mock-classification", object="chat.completion", created=0, model="gpt-6-luna",
                choices=[dict(index=0, finish_reason="stop", message=dict(role="assistant", content=json.dumps(dict(classifications=rows))))],
                usage=dict(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            ))

        api = OpenAI(api_key="offline-key", http_client=httpx.Client(transport=httpx.MockTransport(respond)))
        classifier = ArticleClassifier(settings, client=api, sleep=lambda _: None)
        clients.extend((api, classifier.client))
        notion = notion or FakeNotion()
        llm = llm or Enricher()
        report = run_ingestion(
            settings, options or IngestionOptions(dry_run=True), notion=notion,
            article_classifier=classifier, llm_client=llm,
            collector=lambda _: CollectionResult(articles=pool),
            discovery_factory=discovery_factory, retrieve_article=retrieve, output=lambda _: None,
        )
        return SimpleNamespace(report=report, requests=requests, llm=llm, notion=notion, settings=settings)

    yield make
    for client in clients:
        client.close()


def metadata(run):
    return [row for request in run.requests for row in json.loads(request["messages"][1]["content"])["articles"]]


def test_missing_legacy_keywords_reaches_luna_and_can_win(factory):
    candidate = article("blueberry", BLUEBERRY)
    assert _prepare_candidate(candidate, settings=Settings(), now=NOW).rejection_reason == "no company-topic match"
    result = factory([candidate], classify=lambda _: ("Relevant", 4, "UAE"))
    assert metadata(result)[0]["title"] == BLUEBERRY
    assert result.report.selection.winners[0].target_region == "UAE"


@pytest.mark.parametrize("title", [
    "Saudi water and energy stocks rise with generic economic outlook",
    "Saudi thunderstorms forecast for the coming weekend",
    "West Bank olive farmers face violence during annual harvest",
])
def test_keyword_positive_irrelevant_articles_stop_before_retrieval(factory, title):
    run = factory([article("irrelevant", title)], classify=lambda _: ("Irrelevant", 2, "Global"),
                  retrieve=lambda _: pytest.fail("Rejected metadata must not be retrieved"))
    assert len(metadata(run)) == 1
    assert not run.llm.calls
    assert run.report.evaluation.results[0].rejection_reason == "Luna classified irrelevant"


@pytest.mark.parametrize("title,assigned,hint", [
    ("Iraq in talks with Saudi's ACWA to increase solar capacity", "Global", "KSA"),
    ("Qatar expands domestic poultry production capacity", "Global", "UAE"),
    ("Sharjah invests in water and waste infrastructure", "UAE", "Global"),
    ("Saudi Arabia commissions a battery storage project", "KSA", "UAE"),
    ("Egyptian irrigation project awards contract to UAE firm", "Egypt", "UAE"),
])
def test_classifier_geography_controls_routing_not_source_hints(factory, title, assigned, hint):
    run = factory([article("regional", title, hint=hint)], classify=lambda _: ("Relevant", 4, assigned))
    winner, = run.report.selection.winners
    assert winner.target_region == assigned
    assert winner.article.region == [assigned]
    assert run.llm.calls[0][1] == [assigned]
    assert metadata(run)[0]["source_region_hints_not_evidence"] == [hint]
    assert winner.source_region_hints == [hint]


def test_all_batches_finish_and_merge_before_global_allocation(factory, tmp_path):
    pool = [article(f"item-{index:03}") for index in range(103)]
    # The best article is in the final hash-sorted API batch, not the first 100.
    last = max(pool, key=lambda a: build_url_hash(a.canonical_url))
    seen = []

    def classify(item):
        seen.append(item["article_id"])
        return "Relevant", 5 if item["title"] == last.title else 4, "Global"

    llm = Enricher(before=lambda: len(seen) == 103 or pytest.fail("Enrichment began before all classification results were merged"))
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna", article_enrichment_budget=1, article_enrichment_max_budget=1)
    run = factory(pool, classify=classify, llm=llm, settings=settings)
    assert [len(json.loads(r["messages"][1]["content"])["articles"]) for r in run.requests] == [100, 3]
    assert llm.calls[0][0] == last.title
    assert sum(row.enrichment_attempted for row in run.report.evaluation.results) == 1
    assert len(run.report.evaluation.results) == 103
    assert run.report.evaluation.classification_reports[0].token_usage["total_tokens"] == 300


@pytest.mark.parametrize("malformation", ["missing", "duplicate"])
def test_malformed_ids_recover_in_smaller_batches_before_enrichment(factory, malformation):
    def malformed(_, rows, __):
        if len(rows) == 1:
            return rows
        if malformation == "missing":
            return rows[:-1]
        return [rows[0], rows[0]]

    run = factory([article("one"), article("two")], handler=malformed)
    classification, = run.report.evaluation.classification_reports
    assert classification.request_count == 4  # Two malformed attempts, two singletons.
    assert classification.split_count == 1
    assert classification.failed_ids == []
    assert len(run.llm.calls) == 2


def test_partial_failure_is_visible_and_receives_bounded_assessment(factory, tmp_path):
    def fail_one(payload, rows, _):
        if rows[0]["article_id"] == failed_id:
            return httpx.Response(500, json={"error": {"message": "Offline failure"}})
        return rows

    pool = [article("failure"), article("success")]
    failed_id = build_url_hash(pool[0].canonical_url)
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna", classification_batch_size=1)
    run = factory(pool, handler=fail_one, settings=settings)
    failed = next(r for r in run.report.evaluation.results if r.candidate_id == failed_id)
    assert failed.classification is None and failed.classification_error
    assert failed.enrichment_attempted
    assert failed.target_region == "Global"  # Detailed evidence output, never the UAE source hint.
    assert "detailed evidence" in failed.region_assignment_basis
    assert run.report.evaluation.classification_reports[0].failed_ids == [failed_id]
    audit = build_candidate_audit(run.report)
    assert audit["classification_reports"][0]["request_count"] == 3
    assert any(row["classification_error"] for row in audit["candidates"])


def test_unrecoverable_ids_stay_explicitly_deferred_when_assessment_budget_is_spent(factory, tmp_path):
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna", article_enrichment_budget=1, article_enrichment_max_budget=1)
    run = factory([article("alpha"), article("bravo")], handler=lambda *_: [], settings=settings)
    classification, = run.report.evaluation.classification_reports
    assert len(classification.failed_ids) == 2
    assert len(classification.eligible_ids) == 2
    assert classification.request_count == 6  # 2 * (2*N - 1), bounded binary recovery.
    audit = build_candidate_audit(run.report)
    assert sum(row["enrichment_attempted"] for row in audit["candidates"]) == 1
    deferred, = [row for row in audit["candidates"] if not row["enrichment_attempted"]]
    assert deferred["deferred"] is True
    assert deferred["classification_error"]
    assert deferred["reason"] == "enrichment budget exhausted"


@pytest.mark.parametrize("resolved,expected", [("Egypt", "Egypt"), ("Out of Scope/Unclear", None)])
def test_borderline_unclear_geography_needs_detailed_evidence(factory, resolved, expected):
    run = factory([article("unclear")], classify=lambda _: ("Borderline", 3, "Out of Scope/Unclear"),
                  llm=Enricher(region=resolved))
    candidate, = run.report.evaluation.results
    assert run.llm.calls[0][1] == []
    assert candidate.target_region == expected
    assert bool(run.report.selection.winners) == bool(expected)
    if not expected:
        assert candidate.rejection_reason == "geography unresolved after enrichment"


@pytest.mark.parametrize("score,qualified", [(4, True), (3, False)])
def test_concrete_agricultural_funding_threshold_with_actual_prompt_and_parser(factory, score, qualified):
    captured = []

    def create(**payload):
        captured.append(payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(dict(
            summary="Egypt approves livestock production funding.", why_it_matters="Finances livestock production.",
            relevance_score=score, editorial_significance=2, region=["Egypt"],
            story_type="investment_financing", is_new_development=True,
        ))))])

    client = LlmClient.__new__(LlmClient)
    client.model = "gpt-6-luna"
    client.prompt_directory = Settings().prompt_directory
    client.company_topics = Settings().discovery_topics
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    run = factory([article("veal", VEAL)], classify=lambda _: ("Relevant", 4, "Egypt"), llm=client)
    candidate, = run.report.evaluation.results
    prompt = captured[0]["messages"][-1]["content"]
    assert "Government financing of agricultural/livestock/fisheries production" in prompt
    assert 'need not literally say "food security" or "net zero"' in prompt
    assert "Missing scale" in prompt
    assert candidate.required_relevance_score == 4
    assert candidate.eligible == qualified
    assert bool(run.report.selection.winners) == qualified
    assert candidate.enrichment.editorial_significance == 2
    if not qualified:
        assert candidate.rejection_reason == "relevance below 4"


def test_classifier_score_cannot_override_final_enrichment(factory):
    run = factory([article("strong-metadata")], classify=lambda _: ("Relevant", 5, "UAE"), llm=Enricher(score=3, significance=2))
    assert not run.report.selection.winners
    assert run.report.evaluation.results[0].rejection_reason == "relevance below 4"


def test_unregistered_publisher_still_requires_five(factory):
    run = factory([article("unknown", registered=False)], classify=lambda _: ("Relevant", 5, "UAE"))
    assert run.report.evaluation.results[0].rejection_reason == "relevance below 5"


def test_objective_cleanup_precedes_classification_and_is_audited(factory):
    valid = article("valid")
    alias = replace(valid, url=valid.url + "?utm_source=feed", canonical_url=valid.canonical_url + "/")
    stale = article("stale")
    stale.published_date = NOW - timedelta(days=8)
    unknown = article("unknown-date")
    unknown.published_date = None
    own = article("self")
    own.url = own.canonical_url = "https://www.somamater.com/story"
    invalid = article("invalid-title", "Hi")
    run = factory([valid, alias, stale, unknown, own, invalid])
    assert len(metadata(run)) == 1
    assert len(run.report.evaluation.results) == 6
    audit = build_candidate_audit(run.report)
    assert sum(bool(row["objective_cleanup_reason"]) for row in audit["candidates"]) == 5


def test_processed_url_hash_exclusion_without_saved_url(factory, tmp_path):
    candidate = article("processed")
    state = tmp_path / "state"
    state.mkdir()
    contents = json.dumps({build_url_hash(candidate.url): {"notion_page_id": "old-page"}})
    (state / "seen_articles.json").write_text(contents)
    run = factory([candidate], settings=replace(_settings(state), article_selection_mode="luna"))
    assert not metadata(run)
    assert (state / "seen_articles.json").read_text() == contents
    assert run.report.evaluation.results[0].objective_cleanup_reason == "duplicate or previously processed URL"


@pytest.mark.parametrize("url,title", [
    ("http://[invalid", "Meaningful article headline with evidence"),
    ("https://publisher.example/punctuation", "!!!! ##### *****"),
])
def test_invalid_metadata_never_reaches_model_and_still_has_an_audit(factory, url, title):
    invalid = article("invalid", title)
    invalid.url = invalid.canonical_url = url
    run = factory([invalid])
    assert not run.requests
    assert run.report.audit_path.is_file()
    assert run.report.evaluation.results[0].objective_cleanup_reason


def test_allocator_uses_quality_freshness_and_publisher_diversity(factory, tmp_path):
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna", article_enrichment_budget=2, article_enrichment_max_budget=2)
    strongest = article("best", publisher="same", quality=10)
    repeat = article("repeat", publisher="same", quality=9)
    older = article("older", publisher="other", quality=8)
    older.published_date -= timedelta(hours=1)
    fresher = article("fresher", publisher="other", quality=8)
    run = factory([repeat, older, fresher, strongest], settings=settings)
    assert [title for title, _ in run.llm.calls] == [strongest.title, fresher.title]


def test_shortlist_is_independent_of_input_order(factory, tmp_path):
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna", article_enrichment_budget=3, article_enrichment_max_budget=3)
    pool = [article(key, quality=quality) for key, quality in (("alpha", 7), ("bravo", 9), ("charlie", 8), ("delta", 10))]
    first = factory(deepcopy(pool), settings=settings)
    second = factory(list(reversed(deepcopy(pool))), settings=settings)
    assert first.llm.calls == second.llm.calls
    assert [winner.article.url for winner in first.report.selection.winners] == [winner.article.url for winner in second.report.selection.winners]


def test_discovery_runs_through_same_classifier_and_ignores_query_country(factory):
    found = article("found", "Iraq announces new production capacity", hint="UAE")
    found.discovery_provider = "Brave Search Fallback"
    instances = []

    class Discovery(FakeDiscovery):
        def discover_articles(self, deficits, max_per_region, excluded_hashes):
            self.budget.brave_requests += 1
            self.called_with = deficits, max_per_region
            return [found]

    def discovery_factory(settings, sources):
        instances.append(Discovery(settings, sources))
        return instances[-1]

    run = factory([article("off-topic")],
                  classify=lambda row: ("Irrelevant", 1, "Global") if row["title"].endswith("off-topic") else ("Relevant", 4, "Global"),
                  discovery_factory=discovery_factory)
    assert len(run.requests) == 2
    assert run.report.selection.winners[0].article is found
    assert run.report.selection.winners[0].target_region == "Global"
    assert metadata(run)[1]["source_region_hints_not_evidence"] == ["UAE"]
    assert instances[0].budget.brave_requests == 1
    assert run.report.provider_requests == {"brave": 1, "newsapi": 0}


def test_sufficient_rss_candidates_skip_discovery_and_dry_run_never_writes(factory):
    assigned = {"g": "Global", "u": "UAE", "k": "KSA", "e": "Egypt"}
    pool = [article(key) for key in assigned]

    class NoDiscovery(FakeDiscovery):
        def discover_articles(self, *args, **kwargs):
            pytest.fail("Qualified coverage should avoid discovery requests")

    run = factory(pool, classify=lambda row: ("Relevant", 4, assigned[row["publisher"]]), discovery_factory=NoDiscovery)
    assert len(run.report.selection.winners) == 4
    assert run.notion.creates == run.notion.updates == []
    assert not run.settings.seen_articles_path.exists()
    assert run.report.audit_path.is_file()
    assert not run.report.audit_path.is_relative_to(run.settings.local_state_path)


def test_no_enrich_is_completely_offline_for_both_model_stages(factory):
    run = factory([article("clean")], options=IngestionOptions(dry_run=True, no_enrich=True))
    assert run.requests == run.llm.calls == []
    assert run.notion.creates == run.notion.updates == []
    assert run.report.evaluation.results[0].rejection_reason == "LLM assessment disabled"


def test_legacy_rollback_never_invokes_classifier(factory, tmp_path):
    run = factory([article("legacy", "Global solar grid investment accelerates", hint="Global")],
                  settings=_settings(tmp_path / "state"))
    assert run.requests == []
    assert len(run.report.selection.winners) == 1
    assert run.report.selection_mode == "deterministic"


def test_total_enrichment_budget_covers_feed_and_discovery_failures(factory, tmp_path):
    class Failing(Enricher):
        def enrich_article(self, candidate):
            self.calls.append(candidate.title)
            raise RuntimeError("Offline provider failure")

    class MoreDiscovery(FakeDiscovery):
        def discover_articles(self, *args, **kwargs):
            return [article(f"found-{i}") for i in range(8)]

    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna", article_enrichment_budget=8, article_enrichment_max_budget=8)
    run = factory([article(f"feed-{i}") for i in range(12)], settings=settings, llm=Failing(), discovery_factory=MoreDiscovery)
    assert len(run.llm.calls) == 8
    assert sum(r.enrichment_attempted for r in run.report.evaluation.results) == 8
    assert len(run.report.evaluation.classification_reports) == 2
    assert not run.report.selection.winners


def test_resolved_canonical_aliases_do_not_consume_two_enrichments(factory):
    canonical = "https://publisher.example/resolved"
    run = factory([article("alias-one"), article("alias-two")],
                  retrieve=lambda _: ArticleRetrievalResult(canonical, "resolved_redirect", "extracted", "Full evidence"))
    assert len(run.llm.calls) == 1
    assert any(r.rejection_reason == "duplicate URL" for r in run.report.evaluation.results)


def candidate(key, region="Global", *, publisher=None, score=4, significance=4, title=None):
    return CandidateResult(
        article(key, title=title, publisher=publisher),
        EnrichedArticle("summary", "why", score, editorial_significance=significance), region,
        queue_score=calculate_queue_score(score, 8, significance), source_quality=8,
        required_relevance_score=4,
    )


TARGETS = {"Global": 3, "UAE": 4, "KSA": 3, "Egypt": 2}


def select(pool, *, limit=12, state=None, cap=2, overflow=True):
    return select_final_candidates(pool, weekly_state=state or WeeklyQueueState(), targets=TARGETS,
                                   run_limit=limit, publisher_cap=cap, allow_regional_overflow=overflow)


def regional_pool(counts):
    # Different content words prevent this fixture accidentally testing title dedup.
    names = iter(("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa"))
    return [candidate(next(names), region) for region, count in counts.items() for _ in range(count)]


def test_normal_coverage_precedes_even_higher_scoring_overflow():
    pool = regional_pool(TARGETS)
    extra = candidate("extra", score=5, significance=5)
    result = select([extra, *pool])
    assert result.final_state.region_counts == TARGETS
    assert len(result.winners) == 12
    assert not any(w.regional_overflow for w in result.winners)


def test_coverage_shortfalls_allow_requested_five_three_two_two_overflow():
    counts = {"Global": 5, "UAE": 3, "KSA": 2, "Egypt": 2}
    result = select(regional_pool(counts))
    assert result.final_state.region_counts == counts
    assert len(result.winners) == 12
    assert [w.target_region for w in result.winners if w.regional_overflow] == ["Global", "Global"]
    assert result.shortages == {"Global": 0, "UAE": 1, "KSA": 1, "Egypt": 0}


def test_overflow_respects_run_limit_and_existing_publisher_cap():
    pool = regional_pool({"Global": 5, "UAE": 1})
    capped = candidate("capped", publisher="already-used", score=5)
    state = WeeklyQueueState(publisher_counts={"already-used": 2})
    result = select([*pool, capped], limit=5, state=state)
    assert len(result.winners) == 5
    assert capped not in result.winners
    assert result.rejected_by_constraint["publisher weekly cap"] == 1
    assert any(w.regional_overflow for w in result.winners)


def test_overflow_does_not_exceed_dynamic_publisher_cap_or_select_weak_story():
    pool = [candidate(key, publisher="same") for key in ("alpha", "bravo", "charlie", "delta")]
    pool.append(candidate("weak", score=3))
    result = select(pool)
    assert len(result.winners) == 2
    assert result.final_state.publisher_counts == {"same": 2}
    assert not any(w.article.publisher_key == "weak" for w in result.winners)


def test_overflow_suppresses_same_event_and_existing_queue_event():
    title = "Iraq approves Basra desalination concession with consortium"
    pool = [candidate("first", title=title), candidate("duplicate", title=title + " - Another Outlet"),
            candidate("prior-event", title="Egypt finances Nile irrigation rehabilitation programme")]
    state = WeeklyQueueState(existing_titles=["Egypt finances Nile irrigation rehabilitation programme"])
    state.region_counts["Global"] = 3
    result = select(pool, state=state)
    assert len(result.winners) == 1
    assert result.winners[0].regional_overflow
    assert result.rejected_by_constraint == {"existing event": 1, "same event": 1}


def test_legacy_selector_retains_exact_region_ceilings():
    pool = regional_pool({"Global": 5, "UAE": 3, "KSA": 2, "Egypt": 2})
    result = select(pool, overflow=False)
    assert len(result.winners) == 10
    assert result.final_state.region_counts["Global"] == 3


def test_overflow_is_visible_in_metadata_only_audit(factory, tmp_path):
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna")
    pool = [article(key) for key in ("alpha", "bravo", "charlie")]
    for item in pool:
        item.article_text = "PRIVATE FULL ARTICLE BODY"
    run = factory(pool, settings=settings)
    audit = build_candidate_audit(run.report)
    assert sum(row["regional_overflow"] for row in audit["candidates"]) == 2
    assert all(row["classification_decision"] == "Relevant" for row in audit["candidates"])
    assert all(row["classification_region"] == "Global" for row in audit["candidates"])
    contents = run.report.audit_path.read_text(encoding="utf-8") + json.dumps(audit)
    assert "PRIVATE FULL ARTICLE BODY" not in contents
    assert "Classifier attempted / decision / score / region" in contents
    assert "Overflow" in contents

"""Offline resolver protocol, retrieval and bounded-ingestion contracts."""

from dataclasses import replace
import json
from urllib.parse import parse_qs

import httpx
import pytest

from research_automation.config import Settings
from research_automation.models.article import Article
from research_automation.models.source import Source
from research_automation.pipeline import google_news_resolver as module, ingestion
from research_automation.pipeline.article_retrieval import ArticleRetriever, ArticleRetrievalResult
from research_automation.pipeline.candidate_audit import build_candidate_audit, google_news_resolution_metrics
from research_automation.pipeline.candidate_ranking import evaluate_candidate_pool
from research_automation.pipeline.google_news_resolver import GoogleNewsResolver, GoogleNewsResolvingRetriever
from research_automation.pipeline.ingestion import IngestionOptions, print_ingestion_report
from research_automation.utils.hashing import build_url_hash

from test_ingestion import NOW, _settings
from test_luna_selection import Enricher, factory  # Reuse offline classifier/Notion fixture.


IDENTITY = "CBMiOpaqueArticleId0123456789"
WRAPPER = "https://news.google.com/rss/articles/" + IDENTITY + "?oc=5"
PUBLISHER = "https://publisher.example/news/egypt-expands-water-reuse-capacity"
PARAMS = '<html><div data-n-a-sg="private-signature" data-n-a-ts="1792420000"></div></html>'
SOURCES = [Source("Publisher One", source_url="https://publisher.example", notion_page_id="publisher-1")]


def candidate(url=WRAPPER, title="Egypt expands agricultural water reuse capacity"):
    return Article(title, url, url, "Publisher One", "publisher-1", published_date=NOW,
                   region=["Egypt"], snippet="A new desalination and water reuse investment expands capacity.",
                   source_editorial_quality=8, publisher_key="publisher-1", discovery_method="google_news_rss")


def rpc(url=PUBLISHER):
    return ")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", url])], ["di", 1]])


def standard_response(request):
    return httpx.Response(200, text=PARAMS if request.method == "GET" else rpc())


@pytest.fixture
def google(monkeypatch):
    clients = []

    def make(handler=standard_response):
        requests = []

        def observed(request):
            requests.append(request)
            return handler(request)

        client = httpx.Client(transport=httpx.MockTransport(observed))
        clients.append(client)
        resolver = GoogleNewsResolver(client, sleep=lambda _: None)
        def configured_resolver(**kwargs):
            resolver.max_attempts = kwargs.get("max_attempts", 48)
            return resolver

        monkeypatch.setattr(module, "GoogleNewsResolver", configured_resolver)
        return resolver, requests

    yield make
    for client in clients:
        client.close()


def retrieval_spy(calls, status="insufficient_text"):
    def retrieve(article):
        calls.append((article.url, article.canonical_url))
        return ArticleRetrievalResult(article.canonical_url, "publisher_url", status)
    return retrieve


def test_protocol_signature_identity_transparent_agent_and_request_spacing(google):
    def respond(request):
        if request.method == "POST":
            envelope = json.loads(parse_qs(request.content.decode())["f.req"][0])
            assert envelope[0][0][0] == "Fbv4je"
            inner = json.loads(envelope[0][0][1])
            assert inner[0] == "garturlreq"
            assert inner[2:] == [IDENTITY, 1792420000, "private-signature"]
        return standard_response(request)

    resolver, calls = google(respond)
    now, waits = [0.0], []
    resolver.clock = lambda: now[0]

    def sleep(delay):
        waits.append(delay)
        now[0] += delay

    resolver.sleep = sleep
    result = resolver.resolve(WRAPPER, "publisher.example")
    assert result.status == "resolved" and result.resolved_url == PUBLISHER
    assert result.request_count == 2 and result.attempted and result.latency_seconds == 2
    assert waits == [2.0]
    assert all(c.headers["user-agent"] == "SOMA-MATER-Research/1.0" for c in calls)
    assert parse_qs(calls[0].url.query.decode()) == {"hl": ["en-US"], "gl": ["US"], "ceid": ["US:en"]}


@pytest.mark.parametrize("enabled", [False, True])
def test_flag_controls_integration_and_dry_run_has_no_writes(factory, google, tmp_path, enabled):
    _, google_calls = google()
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna",
                       google_news_url_resolution_enabled=enabled)
    original, retrieved = candidate(), []
    run = factory([original], settings=settings, retrieve=retrieval_spy(retrieved))
    assert retrieved == [(WRAPPER, PUBLISHER if enabled else WRAPPER)]
    assert original.url == WRAPPER
    assert original.canonical_url == (PUBLISHER if enabled else WRAPPER)
    assert len(google_calls) == (2 if enabled else 0)
    assert original.url_hash == build_url_hash(original.canonical_url)
    assert bool(original.google_news_resolution) is enabled
    assert not run.notion.creates and not run.notion.updates
    assert not settings.seen_articles_path.exists()
    if enabled:
        assert original.url_resolution_status == "resolved_google_news"
        audit = build_candidate_audit(run.report)
        assert audit["candidates"][0]["google_news_resolution"]["original_acquisition_method"] == "google_news_rss"
        assert "private-signature" not in json.dumps(audit)


def test_disabled_does_not_even_construct_adapter(factory, monkeypatch):
    monkeypatch.setattr(ingestion, "GoogleNewsResolvingRetriever", lambda *a: pytest.fail("Disabled adapter constructed"))
    calls = []
    run = factory([candidate()], retrieve=retrieval_spy(calls))
    assert calls == [(WRAPPER, WRAPPER)] and not run.report.google_news_url_resolution_enabled


def test_non_google_and_already_resolved_metadata_bypass_decoder():
    class NeverResolve:
        def resolve(self, *args):
            pytest.fail("Direct publisher URL must bypass resolver")

    calls = []
    retrieve = GoogleNewsResolvingRetriever(retrieval_spy(calls), SOURCES, resolver=NeverResolve())
    direct = candidate(PUBLISHER)
    retrieve(direct)
    original = candidate()
    original.canonical_url = PUBLISHER
    retrieve(original)
    assert calls == [(PUBLISHER, PUBLISHER), (WRAPPER, PUBLISHER)]
    assert not direct.google_news_resolution and not original.google_news_resolution


@pytest.mark.parametrize("destination", [
    "", "not a URL", "javascript:alert(1)", "https://publisher.example/",
    "https://publisher.example/news", "https://publisher.example/en/category/water",
    "https://publisher.example/search?q=water", "https://publisher.example/login/continue",
    "https://news.google.com/rss/articles/" + IDENTITY,
    "https://www.google.com/search?q=water",
    "https://other.example/news/a-different-publisher",
    "https://publisher.example.evil.example/news/a-long-article-path",
    "https://user:pass@publisher.example/news/a-long-article-path",
    "https://publisher.example:bad/news/a-long-article-path",
    "http://127.0.0.1/news/a-long-article-path",
])
def test_invalid_destination_falls_back_to_original_wrapper(google, destination):
    _, requests = google(lambda r: httpx.Response(200, text=PARAMS if r.method == "GET" else rpc(destination)))
    calls, original = [], candidate()
    retrieve = GoogleNewsResolvingRetriever(retrieval_spy(calls), SOURCES)
    result = retrieve(original)
    assert calls == [(WRAPPER, WRAPPER)] and result.canonical_url == WRAPPER
    assert original.url == WRAPPER and original.canonical_url == WRAPPER
    assert original.google_news_resolution["status"] == "invalid_destination"
    assert len(requests) == 2


def test_legitimate_publisher_subdomain_is_allowed(google):
    destination = PUBLISHER.replace("publisher.example", "english.publisher.example")
    resolver, _ = google(lambda r: httpx.Response(200, text=PARAMS if r.method == "GET" else rpc(destination)))
    assert resolver.resolve(WRAPPER, "publisher.example").resolved_url == destination


@pytest.mark.parametrize("status", [401, 402, 403, 405, 407, 429, 451])
@pytest.mark.parametrize("on_post", [False, True])
def test_google_refusal_latches_and_falls_back_without_retries(google, status, on_post):
    resolver, requests = google(lambda r: httpx.Response(200, text=PARAMS)
        if on_post and r.method == "GET" else httpx.Response(status))
    retrieve_calls = []
    retrieve = GoogleNewsResolvingRetriever(retrieval_spy(retrieve_calls), SOURCES, resolver=resolver)
    first, second = candidate(), candidate(WRAPPER.replace(IDENTITY, IDENTITY + "second"))
    retrieve(first)
    retrieve(second)
    assert len(requests) == (2 if on_post else 1)
    assert retrieve_calls == [(first.url, first.url), (second.url, second.url)]
    expected = "rate_limited" if status == 429 else "resolution_failed"
    assert first.google_news_resolution["status"] == second.google_news_resolution["status"] == expected
    assert first.google_news_resolution["http_429_count"] == int(status == 429)
    assert second.google_news_resolution["request_count"] == 0
    assert not second.google_news_resolution["attempted"]


@pytest.mark.parametrize("success", [False, True])
def test_normalized_wrapper_cache_keeps_successes_and_failures(google, success):
    resolver, calls = google(standard_response if success else lambda _: httpx.Response(200, text="missing signature"))
    first = resolver.resolve(WRAPPER + "&utm_source=rss", "publisher.example")
    second = resolver.resolve(WRAPPER, "publisher.example")
    assert first.status == second.status == ("resolved" if success else "resolution_failed")
    assert second.cache_hit and not second.attempted and second.request_count == 0
    assert len(calls) == (2 if success else 1)


def test_cached_destination_is_revalidated_for_each_publisher(google):
    resolver, calls = google()
    assert resolver.resolve(WRAPPER, "publisher.example").status == "resolved"
    assert resolver.resolve(WRAPPER, "other.example").status == "invalid_destination"
    assert resolver.resolve(WRAPPER, "publisher.example").status == "resolved"
    assert len(calls) == 2


@pytest.mark.parametrize("success", [True, False])
def test_duplicate_heavy_pool_cannot_expand_decoding_beyond_run_cap(google, success):
    resolver, calls = google(standard_response if success else lambda _: httpx.Response(200, text="missing signature"))
    resolver.max_attempts = 2
    results = [resolver.resolve(WRAPPER.replace(IDENTITY, IDENTITY + str(i)), "publisher.example") for i in range(100)]
    assert resolver.attempt_count == 2
    assert len(calls) == (4 if success else 2)
    assert sum(r.attempted for r in results) == 2
    assert all(r.failure_reason == "resolution_attempt_budget_exhausted" for r in results[2:])
    # A cached prior success/failure remains reusable after the cap.
    assert resolver.resolve(WRAPPER.replace(IDENTITY, IDENTITY + "0"), "publisher.example").cache_hit


def test_resolution_cap_falls_back_without_removing_enrichment_candidate(google):
    resolver, calls = google()
    resolver.max_attempts = 0
    retrieved, original = [], candidate()
    result = GoogleNewsResolvingRetriever(retrieval_spy(retrieved), SOURCES, resolver=resolver)(original)
    assert not calls and retrieved == [(WRAPPER, WRAPPER)]
    assert result.evidence_retrieval_status == "insufficient_text"
    assert original.google_news_resolution["failure_reason"] == "resolution_attempt_budget_exhausted"


@pytest.mark.parametrize("status", [401, 402, 403, 407, 429, 451])
def test_publisher_access_refusal_is_preserved_by_existing_retriever(google, status):
    google()
    calls = []
    with httpx.Client(transport=httpx.MockTransport(lambda r: (calls.append(r) or httpx.Response(status)))) as client:
        retrieve = GoogleNewsResolvingRetriever(ArticleRetriever(client=client).retrieve, SOURCES)
        original = candidate()
        result = retrieve(original)
    assert result.canonical_url == PUBLISHER and result.evidence_retrieval_status == "blocked"
    assert original.google_news_resolution["evidence_status_after"] == "blocked"
    assert len(calls) == 1 and calls[0].url.host == "publisher.example"


def test_normal_publisher_redirect_behavior_has_no_benchmark_article_guard(google):
    google()
    redirect_url = "https://publisher.example/intermediate"
    text = "The new water reuse plant expands agricultural water security capacity. " * 15
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return (httpx.Response(303, headers={"location": redirect_url}) if len(calls) == 1 else
                httpx.Response(200, headers={"content-type": "text/html"}, text=f"<article><h1>New plant</h1><p>{text}</p></article>"))

    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True) as client:
        result = GoogleNewsResolvingRetriever(ArticleRetriever(client=client).retrieve, SOURCES)(candidate())
    assert calls == [PUBLISHER, redirect_url]
    assert result.evidence_retrieval_status == "extracted" and result.canonical_url == redirect_url


@pytest.mark.parametrize("failure", ["timeout", "network", "malformed", "missing", "ambiguous", "oversized"])
def test_protocol_failures_remain_evidence_limited_not_discarded(google, failure):
    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("secret transport detail", request=request)
        if failure == "network":
            raise httpx.ConnectError("secret transport detail", request=request)
        if failure == "missing":
            return httpx.Response(200, text="No signature")
        if failure == "oversized":
            return httpx.Response(200, text="x" * 2_000_001)
        if request.method == "GET":
            return httpx.Response(200, text=PARAMS)
        body = "not json" if failure == "malformed" else json.dumps([["wrb.fr", "Fbv4je", json.dumps(["garturlres", PUBLISHER])]] * 2)
        return httpx.Response(200, text=body)

    _, requests = google(respond)
    calls, original = [], candidate()
    result = GoogleNewsResolvingRetriever(retrieval_spy(calls), SOURCES)(original)
    assert calls == [(WRAPPER, WRAPPER)] and result.evidence_retrieval_status == "insufficient_text"
    assert original.google_news_resolution["status"] == "resolution_failed"
    assert len(requests) <= 2 and "secret" not in json.dumps(original.google_news_resolution)


def test_unexpected_decoder_exception_does_not_interrupt_enrichment(factory, google, tmp_path, monkeypatch):
    resolver, _ = google()
    monkeypatch.setattr(resolver, "resolve", lambda *a: (_ for _ in ()).throw(RuntimeError("private payload")))
    settings = replace(_settings(tmp_path), article_selection_mode="luna", google_news_url_resolution_enabled=True)
    original, calls = candidate(), []
    run = factory([original], settings=settings, retrieve=retrieval_spy(calls))
    assert len(run.llm.calls) == 1 and calls == [(WRAPPER, WRAPPER)]
    assert original.google_news_resolution["failure_reason"] == "resolver_error"


@pytest.mark.parametrize("kind", ["challenge_page", "consent_redirect", "rpc_redirect"])
def test_challenge_or_consent_stops_decoder_for_run_without_following(google, kind):
    def respond(request):
        if kind == "rpc_redirect" and request.method == "GET":
            return httpx.Response(200, text=PARAMS)
        return (httpx.Response(200, text="<title>Sorry - unusual traffic</title>")
                if kind == "challenge_page" else
                httpx.Response(302, headers={"location": "https://consent.google.com/"}))

    resolver, requests = google(respond)
    first = resolver.resolve(WRAPPER, "publisher.example")
    second = resolver.resolve(WRAPPER.replace(IDENTITY, IDENTITY + "another"), "publisher.example")
    assert first.status == second.status == "resolution_failed"
    assert len(requests) == (2 if kind == "rpc_redirect" else 1)
    assert not second.attempted and second.request_count == 0


@pytest.mark.parametrize("loop", [False, True])
def test_only_one_same_identity_google_redirect_is_allowed(google, loop):
    def respond(request):
        if request.method == "GET" and (loop or "/rss/" in request.url.path):
            return httpx.Response(302, headers={"location": "/read/" + IDENTITY})
        return standard_response(request)

    resolver, requests = google(respond)
    result = resolver.resolve(WRAPPER, "publisher.example")
    assert result.status == ("resolution_failed" if loop else "resolved")
    assert len(requests) == (2 if loop else 3)


def test_length_framed_rpc_ignores_unrelated_response_rows(google):
    frame = json.dumps([["wrb.fr", "unrelated", "[]"], ["wrb.fr", "Fbv4je", json.dumps(["garturlres", PUBLISHER])]])
    resolver, _ = google(lambda r: httpx.Response(200, text=PARAMS if r.method == "GET" else
                                                ")]}'\n\n" + str(len(frame)) + "\n" + frame))
    assert resolver.resolve(WRAPPER, "publisher.example").resolved_url == PUBLISHER


def test_publisher_exception_keeps_resolved_identity_and_existing_failure_path(factory, google, tmp_path):
    google()
    settings = replace(_settings(tmp_path), article_selection_mode="luna", google_news_url_resolution_enabled=True)

    def retrieve(article):
        assert article.canonical_url == PUBLISHER
        raise RuntimeError("ordinary retrieval failure")

    original = candidate()
    run = factory([original], settings=settings, retrieve=retrieve)
    assert len(run.llm.calls) == 1 and original.evidence_retrieval_status == "fetch_failed"
    assert original.url_resolution_status == "resolved_google_news"
    assert original.google_news_resolution["evidence_status_after"] == "fetch_failed"
    assert original.url_hash == build_url_hash(PUBLISHER)


def test_direct_resolution_api_bypasses_lookalike_hosts_and_malformed_wrappers(google):
    resolver, requests = google(lambda _: pytest.fail("Invalid wrapper reached network"))
    assert resolver.resolve(PUBLISHER).status == "not_google_news"
    assert resolver.resolve(WRAPPER.replace("news.google.com", "fakenews.google.com")).status == "not_google_news"
    assert resolver.resolve(WRAPPER.replace("https:", "http:")).failure_reason == "invalid_google_wrapper"
    assert resolver.resolve("https://news.google.com/rss/articles/short").failure_reason == "invalid_google_wrapper"
    assert not requests


def test_resolution_only_after_all_classification_and_within_allocated_budget(factory, google, tmp_path):
    classified = []

    def respond(request):
        assert len(classified) == 105, "Resolution started before metadata classification finished"
        return standard_response(request)

    _, requests = google(respond)
    pool = [candidate(WRAPPER.replace(IDENTITY, IDENTITY + str(i)), f"Concrete water project at site {i}") for i in range(105)]

    def classify(item):
        classified.append(item["article_id"])
        return "Relevant", 4, "Egypt"

    settings = replace(_settings(tmp_path), article_selection_mode="luna", google_news_url_resolution_enabled=True,
                       article_enrichment_budget=1, article_enrichment_max_budget=1)
    run = factory(pool, settings=settings, classify=classify, retrieve=retrieval_spy([]))
    assert len(requests) == 2 and len(run.llm.calls) == 1
    assert len(run.requests) == 2  # Metadata batches 100 + 5, unchanged.
    assert sum(bool(a.google_news_resolution) for a in pool) == 1


def test_irrelevant_or_no_enrich_candidates_never_resolve(factory, google, tmp_path):
    _, requests = google()
    settings = replace(_settings(tmp_path), article_selection_mode="luna", google_news_url_resolution_enabled=True)
    run = factory([candidate()], settings=settings, classify=lambda _: ("Irrelevant", 2, "Global"), retrieve=retrieval_spy([]))
    assert not requests and not run.llm.calls
    run = factory([candidate()], settings=settings, options=IngestionOptions(dry_run=True, no_enrich=True), retrieve=retrieval_spy([]))
    assert not requests and not run.llm.calls


def test_wrapper_and_canonical_dedup_and_alias_tracking(factory, google, tmp_path, monkeypatch):
    google()
    tracked = set()
    real_enrich = ingestion.enrich_luna_candidates

    def enrich(*args, **kwargs):
        used = real_enrich(*args, **kwargs)
        tracked.update(kwargs["attempted_urls"])
        return used

    monkeypatch.setattr(ingestion, "enrich_luna_candidates", enrich)
    second_wrapper = WRAPPER.replace(IDENTITY, IDENTITY + "second")
    pool = [candidate(), candidate(second_wrapper, "Egypt signs a water infrastructure finance agreement")]
    settings = replace(_settings(tmp_path), article_selection_mode="luna", google_news_url_resolution_enabled=True)
    run = factory(pool, settings=settings, retrieve=retrieval_spy([]))
    assert len(run.llm.calls) == 1
    assert tracked >= {WRAPPER, second_wrapper, PUBLISHER}
    assert {a.url_hash for a in pool} == {build_url_hash(PUBLISHER)}
    assert any(r.rejection_reason == "duplicate URL" for r in run.report.evaluation.results)


def test_deterministic_path_also_preserves_aliases_for_processed_canonical(google):
    google()
    original, attempted = candidate(), set()
    evaluation = evaluate_candidate_pool([original], deficits={"Egypt": 1}, settings=Settings(),
        enrich=Enricher().enrich_article, retrieve=GoogleNewsResolvingRetriever(retrieval_spy([]), SOURCES),
        now=NOW, excluded_urls={PUBLISHER}, attempted_urls=attempted)
    assert evaluation.results[0].rejection_reason == "duplicate URL"
    assert attempted >= {WRAPPER, PUBLISHER} and original.url_hash == build_url_hash(PUBLISHER)


def test_audit_summary_deduplicates_phases_and_distinguishes_raw_evidence(factory, google, tmp_path):
    google()
    settings = replace(_settings(tmp_path), article_selection_mode="luna", google_news_url_resolution_enabled=True)
    run = factory([candidate()], settings=settings, retrieve=retrieval_spy([], "extracted"))
    run.report.evaluation.results.append(run.report.evaluation.results[0])
    summary = google_news_resolution_metrics(run.report)
    assert summary["wrappers_reaching_enrichment"] == summary["attempted"] == summary["resolved"] == 1
    assert summary["request_count"] == 2 and summary["publisher_bodies_recovered"] == 1
    assert summary["supported_article_bodies_recovered"] is None
    assert summary["evidence_transitions"] == {"not_attempted -> extracted": 1}
    assert summary["selected_resolved_evidence"]["publisher_extracted"] == 1
    lines = []
    print_ingestion_report(run.report, output=lines.append)
    assert any("Google News URL resolution:" in line for line in lines)
    assert any("completeness is unverified" in line for line in lines)


@pytest.mark.parametrize("raw,expected", [(None, False), ("false", False), ("true", True)])
def test_feature_configuration_default_off(monkeypatch, raw, expected):
    from research_automation import config
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("GOOGLE_NEWS_URL_RESOLUTION_ENABLED", raising=False)
    if raw is not None:
        monkeypatch.setenv("GOOGLE_NEWS_URL_RESOLUTION_ENABLED", raw)
    assert config.load_settings().google_news_url_resolution_enabled is expected
    assert Settings().google_news_url_resolution_enabled is False
    assert Settings().direct_site_discovery_enabled is False


def test_invalid_feature_configuration_is_rejected(monkeypatch):
    from research_automation import config
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.setenv("GOOGLE_NEWS_URL_RESOLUTION_ENABLED", "maybe")
    with pytest.raises(ValueError, match="GOOGLE_NEWS_URL_RESOLUTION_ENABLED"):
        config.load_settings()

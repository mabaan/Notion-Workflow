"""Offline supplement, merging and full mocked Luna/Sol ingestion contracts."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json

import httpx
import pytest

from research_automation.models.article import Article
from research_automation.models.source import Source
from research_automation.pipeline import direct_site_discovery as direct
from research_automation.pipeline import ingestion
from research_automation.pipeline.article_classification import prepare_classification_inputs
from research_automation.pipeline.article_retrieval import ArticleRetrievalResult
from research_automation.pipeline.candidate_audit import acquisition_metrics, build_candidate_audit
from research_automation.pipeline.ingestion import IngestionOptions, run_ingestion
from research_automation.utils.hashing import build_url_hash

from test_ingestion import FakeNotion, NOW, _settings, _source_row
from test_luna_selection import factory, metadata


TITLE = "Saudi Arabia approves new desalination plant"
EXTRA_TITLE = "Sharjah commissions wastewater reuse treatment plant"
SOURCE = Source("Arab News", source_url="https://www.arabnews.com", notion_page_id="publisher-1",
                collection_method="Google News RSS", region=["KSA"], editorial_quality=8)
URL = "https://www.arabnews.com/business/saudi-arabia-approves-new-desalination-plant"


def feed_article(title=TITLE, token="original", **kwargs):
    url = "https://news.google.com/rss/articles/" + token
    return Article(title + " - Arab News", url, url, SOURCE.name, SOURCE.notion_page_id,
                   published_date=NOW, collected_date=NOW, source_editorial_quality=8,
                   publisher_key=SOURCE.notion_page_id, region=["KSA"],
                   discovery_method="google_news_rss", discovery_page="https://news.google.com/rss/search?q=site:arabnews.com",
                   date_provenance="rss_entry", **kwargs)


def card(title=TITLE, path=None, date=None):
    path = path or "/business/saudi-arabia-approves-new-desalination-plant"
    date = '<time datetime="' + NOW.isoformat() + '">today</time>' if date is None else date
    return f'<article><a href="{path}"><h2>{title}</h2></a>{date}<p>The plant will supply treated water to local agricultural producers.</p></article>'


def run_supplement(markup, feed=(), sources=(SOURCE,)):
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=markup.encode())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = direct.supplement_articles(list(feed), list(sources), now=NOW, client=client)
    return result, sent


def test_same_feed_headline_prefers_direct_canonical_and_preserves_origin():
    feed = feed_article(snippet="A genuine feed description which has useful additional project details.")
    result, _ = run_supplement(card(), [feed])
    merged, = result.articles
    assert merged.canonical_url == URL
    assert merged.url == feed.url  # preserve processed wrapper identity
    assert merged.discovery_method == "direct_site"
    assert merged.feed_wrapper_replaced
    assert merged.discovery_origins[0]["snippet"] == feed.snippet
    assert merged.discovery_origins[0]["discovery_method"] == "google_news_rss"
    assert merged.discovery_origins[1]["date_raw"] == NOW.isoformat()
    assert feed.canonical_url == feed.url and not feed.feed_wrapper_replaced
    counts = result.sources[SOURCE.name]
    assert counts["direct_feed_headline_matches"] == counts["duplicates_removed"] == counts["wrappers_replaced_by_direct_urls"] == 1


def test_feed_only_and_recent_direct_only_articles_both_remain():
    original = feed_article("Egypt approves funding for National Veal Project")
    result, _ = run_supplement(card(EXTRA_TITLE), [original])
    assert result.articles[0] is original
    assert result.articles[1].title == EXTRA_TITLE
    assert result.articles[1].date_provenance == "listing_card"
    assert result.sources[SOURCE.name]["direct_only_candidates"] == 1


@pytest.mark.parametrize("date", ["", '<time datetime="2026-08-20T10:00:00Z">old</time>', '<time datetime="2026-09-02T10:00:00Z">future</time>', '<time datetime="2026-09-01T08:00:00">unzon ed</time>'])
def test_undated_stale_future_and_unzoned_direct_articles_rejected(date):
    feed = feed_article()
    result, _ = run_supplement(card(date=date), [feed])
    assert result.articles == [feed]
    assert result.sources[SOURCE.name]["recent_direct_candidates_accepted"] == 0


def test_seven_day_window_includes_six_day_old_article_but_excludes_boundary_day_without_time():
    date = '<time datetime="' + (NOW-timedelta(days=6)).isoformat() + '">six days</time>'
    result, _ = run_supplement(card(date=date))
    assert len(result.articles) == 1
    date = '<time datetime="' + (NOW-timedelta(days=7)).date().isoformat() + '">boundary day</time>'
    assert run_supplement(card(date=date))[0].articles == []


def test_non_article_external_and_navigation_links_rejected():
    markup = ''.join(card(path=p) for p in ["/authors/long-author-profile-name", "/en/topic/interesting-energy-news", "/assets/long-image-file-name.jpg", "https://evil.example/news/foreign-long-news-headline"])
    markup += '<nav>' + card() + '</nav>'
    assert run_supplement(markup)[0].articles == []


def test_neighbour_card_cannot_supply_missing_date():
    markup = '<div>' + card() + card(EXTRA_TITLE, "/business/sharjah-water-reuse-treatment-plant", date="") + '</div>'
    result, _ = run_supplement(markup)
    assert len(result.articles) == 1


def test_relative_dates_in_plain_spans_and_national_path_provenance():
    result, _ = run_supplement(card(date='<span class="st-h-m-nf">2h ago</span>'))
    assert result.articles[0].published_date == NOW-timedelta(hours=2)
    assert result.articles[0].date_precision == "relative"
    national = Source("The National", source_url="https://www.thenationalnews.com", notion_page_id="national")
    result, _ = run_supplement(card(path="/news/2026/09/01/saudi-arabia-approves-new-desalination-plant", date=""), sources=[national])
    article, = result.articles
    assert article.published_date.date() == NOW.date()
    assert article.date_precision == "day"
    assert article.date_provenance == "literal_url_path; apparent publication day only"


def test_acceptance_and_anchor_caps_do_not_crawl_more_pages():
    markup = ''.join(card(path=f"/business/saudi-water-treatment-plant-{i}") for i in range(60))
    result, sent = run_supplement(markup)
    assert len(sent) == 1 and len(result.articles) == 20
    assert result.sources[SOURCE.name]["candidate_anchors_considered"] == 20
    markup = card(date="") * 105 + card(path="/news/dated-story-after-the-cap")
    result, _ = run_supplement(markup)
    assert result.sources[SOURCE.name]["candidate_anchors_considered"] == 100
    assert result.articles == []


@pytest.mark.parametrize("status", [302, 401, 403, 405, 429, 500])
def test_listing_status_failure_does_not_retry_follow_or_remove_feed(status):
    sent, feed = [], feed_article()

    def respond(request):
        sent.append(request)
        return httpx.Response(status, headers={"location": "/another-listing"})
    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True) as client:
        result = direct.supplement_articles([feed], [SOURCE], now=NOW, client=client)
    assert len(sent) == result.sources[SOURCE.name]["listing_requests"] == 1
    assert result.articles == [feed]
    assert result.sources[SOURCE.name]["status"] != "success"
    assert sent[0].headers["user-agent"] == "SOMA-MATER-Research/1.0"


def test_one_source_failure_does_not_stop_other_source_or_feeds():
    second = Source("Saudi Gazette", source_url="https://saudigazette.com.sa", notion_page_id="sg")
    feed = feed_article()

    def respond(request):
        if "arabnews" in request.url.host:
            raise httpx.ConnectError("offline failure", request=request)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=card())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = direct.supplement_articles([feed], [SOURCE, second], now=NOW, client=client)
    assert result.articles[0] is feed and len(result.articles) == 2
    assert result.sources[SOURCE.name]["status"] == "failed"
    assert result.sources[second.name]["status"] == "success"


def test_only_four_allowlisted_publishers_and_valid_registry_urls_are_contacted():
    excluded = [Source(name, source_url="https://www.reuters.com") for name in ["Reuters", "S&P Global", "The Guardian International", "Nature"]]
    result, sent = run_supplement(card(), sources=excluded)
    assert not sent and not result.articles
    result, sent = run_supplement(card(), sources=[replace(SOURCE, source_url="https://attacker.example")])
    assert not sent and result.sources[SOURCE.name]["status"] == "invalid_source_url"
    assert len(run_supplement(card(), sources=[SOURCE, SOURCE])[1]) == 1


def test_ambiguous_multiple_direct_pages_keep_feed_and_all_direct_candidates():
    result, _ = run_supplement(card() + card(path="/news/another-page-for-the-same-headline"), [feed_article()])
    assert len(result.articles) == 3
    assert result.sources[SOURCE.name]["wrappers_replaced_by_direct_urls"] == 0
    assert result.sources[SOURCE.name]["ambiguous_matches_retained"] == 2
    assert result.sources[SOURCE.name]["direct_only_candidates"] == 0


def test_ambiguous_multiple_feed_wrappers_are_not_arbitrarily_resolved():
    result, _ = run_supplement(card(), [feed_article(token="one"), feed_article(token="two")])
    assert len(result.articles) == 3


def test_related_headlines_and_same_headline_on_distant_dates_remain_separate():
    feed = feed_article("Saudi Arabia opens new desalination plant")
    assert len(run_supplement(card(), [feed])[0].articles) == 2
    feed = replace(feed_article(), published_date=NOW-timedelta(days=3))
    assert len(run_supplement(card(), [feed])[0].articles) == 2


def test_already_direct_feed_canonical_and_acquisition_metadata_are_preserved():
    original = replace(feed_article(), url=URL, canonical_url=URL, discovery_method="rss")
    result, _ = run_supplement(card(), [original])
    merged, = result.articles
    assert merged.canonical_url == URL and merged.discovery_method == "rss"
    assert merged.discovery_page == original.discovery_page
    assert not merged.feed_wrapper_replaced


def test_same_direct_url_can_fill_a_missing_feed_publication_date():
    original = replace(feed_article(), url=URL, canonical_url=URL, published_date=None)
    result, _ = run_supplement(card(), [original])
    merged, = result.articles
    assert merged.published_date == NOW
    assert merged.date_provenance == "listing_card"


def test_processed_original_wrapper_is_excluded_even_after_canonical_replacement():
    feed = feed_article()
    merged = run_supplement(card(), [feed])[0].articles
    prepared = prepare_classification_inputs(merged, now=NOW, seen_url_hashes=[build_url_hash(feed.url)])
    assert not prepared.inputs
    assert prepared.excluded[0].reason == "duplicate or previously processed URL"


def test_invalid_feed_url_does_not_abort_merge_or_hide_valid_direct_input():
    original = replace(feed_article(), url="http://[invalid", canonical_url="http://[invalid")
    result, _ = run_supplement(card(), [original])
    assert result.articles[0] is original and len(result.articles) == 2
    prepared = prepare_classification_inputs(result.articles, now=NOW)
    assert len(prepared.inputs) == 1
    assert prepared.excluded[0].reason == "invalid URL"


def _notion():
    row = _source_row()
    row["properties"]["Source Name"]["title"][0]["plain_text"] = SOURCE.name
    row["properties"]["Source URL"]["url"] = SOURCE.source_url
    row["properties"]["Collection Method"]["select"]["name"] = "Google News RSS"
    return FakeNotion(source_rows=[row])


def test_direct_and_feed_candidates_enter_same_luna_call_then_enrichment_without_writes(factory, monkeypatch, tmp_path):
    markup = card() + card(EXTRA_TITLE, "/business/sharjah-water-reuse-treatment-plant")
    sent = []

    def collect(feed, sources, **kwargs):
        assert len(feed) == 2  # configured feed collection ran first
        with httpx.Client(transport=httpx.MockTransport(lambda r: (sent.append(r) or httpx.Response(200, headers={"content-type": "text/html"}, text=markup)))) as client:
            return direct.supplement_articles(feed, sources, client=client, **kwargs)
    monkeypatch.setattr(ingestion, "supplement_articles", collect)
    settings = replace(_settings(tmp_path / "state"), article_selection_mode="luna", llm_model="gpt-6-sol", direct_site_discovery_enabled=True)
    feed = [feed_article(), feed_article("Egypt approves funding for National Veal Project", "feed-only")]
    run = factory(feed, settings=settings, notion=_notion(), retrieve=lambda a: ArticleRetrievalResult(a.canonical_url, "publisher_url", "extracted", "Supported article body. " * 30))
    inputs = metadata(run)
    assert len(inputs) == 3 and {x["title"] for x in inputs} == {feed[0].title, feed[1].title, EXTRA_TITLE}
    assert len(sent) == 1
    rows = run.report.evaluation.results
    matched = next(r for r in rows if r.article.feed_wrapper_replaced)
    assert matched.article.canonical_url == URL and matched.classification_attempted and matched.enrichment_attempted
    assert run.notion.creates == run.notion.updates == []
    assert not settings.seen_articles_path.exists()
    audit = build_candidate_audit(run.report)
    counts = audit["direct_site_discovery"]["sources"][SOURCE.name]
    assert counts["feed_candidates_collected"] == 2
    assert counts["recent_direct_candidates_accepted"] == 2
    assert counts["luna_attempted"] == 2 and counts["retriever_extracted"] == 2
    assert counts["wrappers_replaced_by_direct_urls"] == 1
    assert counts["direct_only_candidates"] == 1
    matched_audit = next(row for row in audit["candidates"] if row["feed_wrapper_replaced"])
    assert all("snippet" not in origin for origin in matched_audit["discovery_origins"])
    assert audit["acquisition_metrics"]["google_news_rss"]["candidates"] == 1
    assert run.report.audit_path.exists()
    md = run.report.audit_path.read_text(encoding="utf8")
    assert "Direct-site supplement (shadow only)" in md and "listing_card" in md


def test_flag_false_is_identical_legacy_path_and_never_calls_supplement(factory, monkeypatch):
    feed = [feed_article()]
    baseline = factory(deepcopy(feed), notion=_notion())
    monkeypatch.setattr(ingestion, "supplement_articles", lambda *a, **k: pytest.fail("disabled supplement called"))
    unchanged = factory(deepcopy(feed), notion=_notion())
    assert baseline.requests == unchanged.requests
    assert [r.article.canonical_url for r in baseline.report.evaluation.results] == [r.article.canonical_url for r in unchanged.report.evaluation.results]
    assert baseline.report.selection.tier_counts == unchanged.report.selection.tier_counts
    assert baseline.llm.calls == unchanged.llm.calls
    assert not unchanged.report.direct_site_discovery


def test_enabled_flag_rejects_live_run_before_notion_or_feed_activity(tmp_path):
    settings = replace(_settings(tmp_path), direct_site_discovery_enabled=True)
    with pytest.raises(ValueError, match="shadow-only.*--dry-run"):
        run_ingestion(settings, IngestionOptions(), notion=object(), collector=lambda _: pytest.fail("feed must not run"))


def test_oversized_listing_keeps_feed_and_does_not_request_articles():
    original = feed_article()
    result, sent = run_supplement("x" * (direct.MAX_RESPONSE_BYTES + 1), [original])
    assert len(sent) == 1
    assert result.articles == [original]
    assert result.sources[SOURCE.name]["status"] == "failed"


def test_failed_supplement_still_classifies_feed_in_shadow_mode(factory, monkeypatch, tmp_path):
    def collect(feed, sources, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403))) as client:
            return direct.supplement_articles(feed, sources, client=client, **kwargs)
    monkeypatch.setattr(ingestion, "supplement_articles", collect)
    settings = replace(_settings(tmp_path), article_selection_mode="luna", direct_site_discovery_enabled=True)
    run = factory([feed_article()], settings=settings, notion=_notion())
    assert len(metadata(run)) == 1
    audit = build_candidate_audit(run.report)
    counts = audit["direct_site_discovery"]["sources"][SOURCE.name]
    assert counts["status"] == "failed" and counts["recent_direct_candidates_accepted"] == 0
    assert counts["luna_attempted"] == counts["selected"] == 0  # direct only; feed still assessed
    assert audit["acquisition_metrics"]["google_news_rss"]["luna_attempted"] == 1
    assert run.notion.creates == run.notion.updates == []

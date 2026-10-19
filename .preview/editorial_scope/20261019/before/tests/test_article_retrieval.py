from datetime import UTC, datetime

import httpx
import pytest

from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.source import Source
from research_automation.pipeline.article_retrieval import (
    ArticleRetrievalResult,
    ArticleRetriever,
)
from research_automation.pipeline.candidate_ranking import evaluate_candidate_pool
from research_automation.sources.rss import RssSource
from research_automation.utils.hashing import build_url_hash


NOW = datetime(2026, 10, 14, tzinfo=UTC)
GOOGLE_URL = "https://news.google.com/rss/articles/example"
PUBLISHER_URL = "https://publisher.example/news/battery-project"


def _article(*, url: str = PUBLISHER_URL) -> Article:
    return Article(
        title="Egypt battery assembly project advances",
        url=url,
        canonical_url=url,
        source_name="Publisher",
        source_page_id="publisher-1",
        published_date=NOW,
        snippet="The proposed facility would assemble batteries in Egypt.",
        region=["Egypt"],
        publisher_key="publisher-1",
    )


def _sample_html(*, canonical_url: str = PUBLISHER_URL) -> str:
    paragraph = (
        "The proposed Egypt battery assembly facility would have annual capacity "
        "of 500 MWh. The named developer said negotiations remain under way and "
        "construction has not started. The project targets commercial production "
        "after regulatory approvals and a final investment decision. "
    )
    return f"""
    <html>
      <head>
        <title>Egypt battery project</title>
        <link rel="canonical" href="{canonical_url}?utm_source=feed">
      </head>
      <body><article><h1>Egypt battery project</h1><p>{paragraph * 3}</p></article></body>
    </html>
    """


def test_rss_preserves_google_feed_link_when_metadata_has_publisher_url(
    monkeypatch,
) -> None:
    feed = f"""
    <rss version="2.0"><channel><title>News</title><item>
      <title>Egypt battery project advances</title>
      <link>{GOOGLE_URL}</link>
      <description><![CDATA[
        <a href="{PUBLISHER_URL}">Egypt battery project advances</a>
      ]]></description>
      <pubDate>Wed, 14 Oct 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>
    """.encode()
    monkeypatch.setattr(
        "research_automation.sources.rss.fetch_feed_bytes",
        lambda _: feed,
    )
    source = Source(
        name="Publisher",
        feed_url="https://news.google.com/rss/search?q=publisher",
        collection_method="Google News RSS",
        notion_page_id="publisher-1",
    )

    article = RssSource(source).collect()[0]

    assert article.url == GOOGLE_URL
    assert article.canonical_url == PUBLISHER_URL
    assert article.url_resolution_status == "resolved_feed_metadata"


def test_google_news_redirect_resolves_to_publisher_canonical_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "news.google.com":
            return httpx.Response(302, headers={"location": PUBLISHER_URL})
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=_sample_html(),
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        result = ArticleRetriever(client=client).retrieve(_article(url=GOOGLE_URL))

    assert result.canonical_url == PUBLISHER_URL
    assert result.url_resolution_status == "resolved_canonical"
    assert result.evidence_retrieval_status == "extracted"
    assert "500 MWh" in result.article_text


def test_unresolved_google_news_link_retains_original_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><body>Google News consent required.</body></html>",
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    ) as client:
        result = ArticleRetriever(client=client).retrieve(_article(url=GOOGLE_URL))

    assert result.canonical_url == GOOGLE_URL
    assert result.url_resolution_status == "unresolved"
    assert result.evidence_retrieval_status == "insufficient_content"
    assert result.article_text == ""


def test_article_text_extraction_preserves_capacity_and_project_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=_sample_html(),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ArticleRetriever(client=client).retrieve(_article())

    assert result.evidence_retrieval_status == "extracted"
    assert "annual capacity of 500 MWh" in result.article_text
    assert "negotiations remain under way" in result.article_text


@pytest.mark.parametrize(
    ("status_code", "body", "expected_status"),
    [
        (403, "Access denied", "blocked"),
        (404, "Missing", "fetch_failed"),
        (200, "<html><body><p>Short notice.</p></body></html>", "insufficient_content"),
    ],
)
def test_missing_blocked_or_insufficient_content_falls_back_cleanly(
    status_code: int,
    body: str,
    expected_status: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            headers={"content-type": "text/html"},
            text=body,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ArticleRetriever(client=client).retrieve(_article())

    assert result.evidence_retrieval_status == expected_status
    assert result.article_text == ""


def test_final_canonical_url_drives_hash_while_original_url_is_preserved() -> None:
    article = _article(url=GOOGLE_URL)

    def retrieve(_article: Article) -> ArticleRetrievalResult:
        return ArticleRetrievalResult(
            canonical_url=PUBLISHER_URL,
            url_resolution_status="resolved_redirect",
            evidence_retrieval_status="extracted",
            article_text="Evidence " * 100,
        )

    evaluation = evaluate_candidate_pool(
        [article],
        deficits={"Global": 0, "UAE": 0, "KSA": 0, "Egypt": 1},
        settings=Settings(
            article_shortlist_initial_per_region=1,
            article_shortlist_max_per_region=1,
            article_queue_weekly_target_global=1,
            article_queue_weekly_target_uae=1,
            article_queue_weekly_target_ksa=1,
            article_queue_weekly_target_egypt=1,
        ),
        enrich=lambda _: EnrichedArticle("Summary", "Why", 5),
        retrieve=retrieve,
        now=NOW,
    )

    assert [result for result in evaluation.results if result.eligible]
    assert article.url == GOOGLE_URL
    assert article.canonical_url == PUBLISHER_URL
    assert article.url_hash == build_url_hash(PUBLISHER_URL)


def test_retrieval_runs_only_for_the_bounded_shortlist() -> None:
    articles = [
        Article(
            title=f"Global solar project {index} advances",
            url=f"https://publisher-{index}.example/story",
            canonical_url=f"https://publisher-{index}.example/story",
            source_name=f"Publisher {index}",
            source_page_id=f"publisher-{index}",
            published_date=NOW,
            snippet="Global renewable solar capacity investment.",
            region=["Global"],
            publisher_key=f"publisher-{index}",
        )
        for index in range(3)
    ]
    retrieved = []

    def retrieve(article: Article) -> ArticleRetrievalResult:
        retrieved.append(article.title)
        return ArticleRetrievalResult(
            article.canonical_url,
            "publisher_url",
            "insufficient_content",
        )

    evaluate_candidate_pool(
        articles,
        deficits={"Global": 1, "UAE": 0, "KSA": 0, "Egypt": 0},
        settings=Settings(
            article_shortlist_initial_per_region=1,
            article_shortlist_max_per_region=1,
            article_queue_weekly_target_global=1,
            article_queue_weekly_target_uae=1,
            article_queue_weekly_target_ksa=1,
            article_queue_weekly_target_egypt=1,
        ),
        enrich=lambda _: EnrichedArticle("Summary", "Why", 5),
        retrieve=retrieve,
        now=NOW,
    )

    assert len(retrieved) == 1

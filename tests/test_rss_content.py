"""Offline feed evidence checks, including the user-supplied AGBI download."""

from datetime import UTC, datetime
import json
from pathlib import Path

import feedparser
import httpx
import pytest

from research_automation.clients.llm_client import LlmClient
from research_automation.config import Settings
from research_automation.models.source import Source
from research_automation.pipeline.article_retrieval import (
    MAX_RESPONSE_BYTES,
    MAX_TEXT_CHARS,
    MINIMUM_TEXT_CHARS,
    ArticleRetriever,
    extract_feed_article_text,
)
from research_automation.pipeline.candidate_ranking import evaluate_candidate_pool
from research_automation.pipeline.collect import collect_articles
from research_automation.pipeline.draft import (
    format_newsletter_articles_for_prompt,
    format_social_articles_for_prompt,
    load_weekly_draft_articles,
)
from research_automation.pipeline.draft_validation import (
    validate_newsletter_draft,
    validate_social_draft,
)
from research_automation.pipeline.notion_write import create_article_queue_page
from research_automation.sources.rss import RssSource
from research_automation.utils.evidence import FEED_CONTENT_LIMITATION
from research_automation.utils.hashing import build_content_hash, build_url_hash
from research_automation.utils.urls import clean_url


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests/fixtures/agbi_feed_sample_2026-10-15.xml"
URL = "https://publisher.example/egypt-battery"
NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)
BODY = """
<p>Egypt is negotiating a battery assembly facility with proposed annual capacity
of 500 MWh. The developer said construction has not started and a final investment
decision is still pending.</p>
<p>The proposed facility would supply storage equipment for renewable energy
projects. Financing and regulatory approvals are required before work can begin.</p>
<p>The company expects to announce a timetable after negotiations conclude.
No operational capacity or completion date has been confirmed.</p>
"""


def _source(name="Publisher", url="https://publisher.example/feed/") -> Source:
    return Source(
        name=name,
        feed_url=url,
        collection_method="RSS",
        notion_page_id="publisher-1",
        region=["Egypt"],
        topic_focus=["energy transition"],
        editorial_quality=8,
    )


def _feed(content=BODY, *, duplicate=False, description="Egypt battery project proposed."):
    encoded = (
        f"<content:encoded><![CDATA[{content}]]></content:encoded>"
        if content is not None else ""
    )
    item = f"""
    <item><title>Egypt battery assembly project proposed</title>
    <link>{URL}?utm_source=rss</link>
    <pubDate>Thu, 15 Oct 2026 10:00:00 GMT</pubDate>
    <description><![CDATA[{description}]]></description>{encoded}</item>
    """
    return f"""<rss version="2.0"
    xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel><title>Publisher</title>{item * (2 if duplicate else 1)}</channel>
    </rss>""".encode()


def _collect(monkeypatch, data=None):
    monkeypatch.setattr(
        "research_automation.sources.rss.fetch_feed_bytes",
        lambda _: data if data is not None else _feed(),
    )
    return RssSource(_source()).collect()


def test_encoded_html_cleaning_removes_non_article_elements_and_decodes_entities():
    html = """
    <script>SECRET_SCRIPT</script><style>SECRET_STYLE</style>
    <nav>Navigation</nav><footer>Footer</footer><aside>Related stories</aside>
    <form>Subscribe</form><div hidden>Hidden content</div>
    <div role="navigation">Menu</div><iframe>Frame content</iframe>
    <p>Water &amp; energy&nbsp;security &#8211; planned investment.</p>
    """ + BODY
    text = extract_feed_article_text(html)

    assert "Water & energy security – planned investment." in text
    assert "500 MWh" in text
    assert "decision is still pending" in text
    for removed in (
        "SECRET_SCRIPT", "SECRET_STYLE", "Navigation", "Footer", "Related stories",
        "Subscribe", "Hidden content", "Menu", "Frame content",
    ):
        assert removed not in text
    assert "<" not in text
    assert "\n" not in text
    assert "  " not in text


def test_rss_content_preserves_metadata_snippet_and_publisher_url(monkeypatch):
    article = _collect(monkeypatch)[0]

    assert article.article_text == extract_feed_article_text(BODY)
    assert article.evidence_retrieval_status == "feed_content"
    assert article.snippet == "Egypt battery project proposed."
    assert article.url == article.canonical_url == URL
    assert article.canonical_url != _source().feed_url
    assert article.source_name == "Publisher"
    assert article.source_page_id == article.publisher_key == "publisher-1"
    assert article.published_date == datetime(2026, 10, 15, 10, tzinfo=UTC)
    assert article.region == ["Egypt"]
    assert article.topic_focus == ["energy transition"]
    assert article.source_editorial_quality == 8


@pytest.mark.parametrize("content", [None, "", "<p>Short excerpt. Read more.</p>"])
@pytest.mark.parametrize("page_status", [200, 403])
def test_missing_or_short_feed_content_keeps_page_and_snippet_fallbacks(
    monkeypatch, content, page_status,
):
    article = _collect(monkeypatch, _feed(content))[0]
    assert article.article_text == ""
    assert article.evidence_retrieval_status == "not_attempted"
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            page_status, headers={"content-type": "text/html"},
            text=f"<html><body><article>{BODY}</article></body></html>",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = ArticleRetriever(client=client).retrieve(article)

    assert calls == [URL]
    assert result.evidence_retrieval_status == ("extracted" if page_status == 200 else "blocked")
    assert bool(result.article_text) == (page_status == 200)
    assert article.snippet == "Egypt battery project proposed."


def test_long_description_alone_is_not_promoted_to_feed_article_evidence(monkeypatch):
    article = _collect(monkeypatch, _feed(None, description=BODY))[0]
    assert article.snippet
    assert article.article_text == ""
    assert article.evidence_retrieval_status == "not_attempted"


def test_feed_content_uses_existing_size_and_length_limits(monkeypatch):
    assert extract_feed_article_text("x" * (MINIMUM_TEXT_CHARS - 1)) == ""
    assert len(extract_feed_article_text("x" * MINIMUM_TEXT_CHARS)) == MINIMUM_TEXT_CHARS
    assert extract_feed_article_text("é" * (MAX_RESPONSE_BYTES // 2 + 1)) == ""
    article = _collect(monkeypatch, _feed(BODY * 100))[0]
    assert len(article.article_text) == MAX_TEXT_CHARS

    # A caller's stricter retrieval text ceiling also applies to feed evidence.
    result = ArticleRetriever(max_text_chars=400).retrieve(article)
    assert len(result.article_text) == 400
    assert result.evidence_retrieval_status == "feed_content"


def test_downloaded_agbi_sample_parses_all_entries_offline(monkeypatch):
    data = SAMPLE.read_bytes()
    parsed = feedparser.parse(data)
    assert not parsed.bozo
    assert parsed.version == "rss20"
    assert len(parsed.entries) == 10
    assert all(entry.get("content") for entry in parsed.entries)
    articles = _collect(monkeypatch, data)

    assert len(articles) == 10
    assert len({article.canonical_url for article in articles}) == 10
    for article, entry in zip(articles, parsed.entries):
        assert article.evidence_retrieval_status == "feed_content"
        assert MINIMUM_TEXT_CHARS <= len(article.article_text) <= MAX_TEXT_CHARS
        assert article.url == article.canonical_url == clean_url(entry.link)
        assert article.published_date is not None
        assert article.snippet


def test_feed_evidence_reaches_existing_single_enrichment_without_page_request(
    monkeypatch,
):
    articles = _collect(monkeypatch, _feed(duplicate=True))
    prompts = []
    requests = []
    llm = LlmClient(
        provider="openai", model="test-model", api_key="test-key",
        prompt_directory=ROOT / "src/research_automation/prompts",
    )

    def generate(prompt):
        prompts.append(prompt)
        return {
            "summary": "A battery facility is proposed in Egypt.",
            "why_it_matters": "It would add storage manufacturing capacity.",
            "relevance_score": 5, "editorial_significance": 4,
            "significance_reason": "Proposed annual capacity is 500 MWh.",
            "factual_points": ["Proposed annual capacity is 500 MWh."],
            "topic": ["energy transition"], "region": ["Egypt"],
            "newsletter_angle": "Proposed storage capacity", "sns_hook": "Battery proposal",
        }

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(403)

    monkeypatch.setattr(llm, "_generate_json", generate)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        evaluation = evaluate_candidate_pool(
            articles, deficits={"Egypt": 1}, settings=Settings(),
            enrich=llm.enrich_article, retrieve=ArticleRetriever(client=client).retrieve,
            now=NOW,
        )

    assert requests == []
    assert len(prompts) == 1
    assert extract_feed_article_text(BODY) in prompts[0]
    assert FEED_CONTENT_LIMITATION in prompts[0]
    eligible = [result for result in evaluation.results if result.eligible]
    assert len(eligible) == 1
    result = eligible[0]
    assert result.enrichment.relevance_score == 5
    assert result.enrichment.editorial_significance == 4
    assert result.enrichment.newsletter_angle == "Proposed storage capacity"
    assert result.enrichment.sns_hook == "Battery proposal"
    assert result.article.url == result.article.canonical_url == URL
    assert result.article.url_hash == build_url_hash(URL)
    assert result.article.content_hash == build_content_hash(result.article.title, "Publisher")
    assert evaluation.rejection_counts["duplicate URL"] == 1

    # Notion is an in-memory double; no connected clients or live writes are used.
    notion = _MemoryNotion()
    create_article_queue_page(notion, "articles", result.article, "dataset", enriched=result.enrichment)
    serialized = json.dumps(notion.page) + json.dumps(notion.children)
    assert "Feed Content" in serialized
    assert FEED_CONTENT_LIMITATION in serialized
    assert result.article.article_text not in serialized
    assert "Financing and regulatory approvals" not in serialized
    draft_article = load_weekly_draft_articles(
        notion, Settings(notion_article_queue_database_id="articles"),
        "dataset", ["Use in Newsletter"],
    )[0]
    assert draft_article.evidence_retrieval_status == "Feed Content"
    assert draft_article.resolved_publisher_url == URL
    assert draft_article.factual_points == ["Proposed annual capacity is 500 MWh."]
    for formatter in (format_newsletter_articles_for_prompt, format_social_articles_for_prompt):
        context = formatter([draft_article])
        assert FEED_CONTENT_LIMITATION in context
        assert "Factual evidence (primary" in context
        assert "Proposed annual capacity is 500 MWh." in context
        assert "Full-article evidence is unavailable" not in context
    for validator in (validate_newsletter_draft, validate_social_draft):
        warnings = validator("", [draft_article])
        assert any(FEED_CONTENT_LIMITATION in warning for warning in warnings)
        assert not any("factual checks are limited" in warning for warning in warnings)


class _MemoryNotion:
    def create_page(self, database_id, properties, children):
        # Add the read-side text fields that real Notion responses include.
        for value in properties.values():
            for field in ("title", "rich_text"):
                for item in value.get(field, []):
                    item["plain_text"] = item["text"]["content"]
        self.page = {"id": "article-1", "properties": properties}
        self.children = children
        return self.page

    def query_database(self, *args, **kwargs):
        return [self.page]

    def list_block_children(self, page_id):
        return self.children

    def retrieve_page(self, page_id):
        return {"properties": {"Source Name": {"title": [{"plain_text": "Publisher"}]}}}


@pytest.mark.parametrize("status", [403, 405])
def test_agbi_http_failure_is_not_retried_and_other_sources_continue(monkeypatch, status):
    calls = []
    original_client = httpx.Client

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(status) if request.url.host == "www.agbi.com" else httpx.Response(200, content=_feed())

    monkeypatch.setattr(
        "research_automation.sources.rss.httpx.Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = collect_articles(
        [_source("AGBI", "https://www.agbi.com/feed/"), _source()], max_workers=1,
    )
    assert calls.count("https://www.agbi.com/feed/") == 1
    assert len(result.articles) == 1
    assert {attempt.source_name: attempt.outcome for attempt in result.attempts} == {
        "AGBI": "HTTP Error", "Publisher": "Success",
    }
    assert str(status) in result.source_errors[0]


def test_substantial_excerpt_is_usable_but_never_claimed_as_a_complete_article(monkeypatch):
    article = _collect(monkeypatch, _feed(BODY + "<p>Read the full story on our website.</p>"))[0]

    def unexpected_client(**kwargs):
        pytest.fail("Feed evidence must not construct an HTTP client for the article page")

    monkeypatch.setattr("research_automation.pipeline.article_retrieval.httpx.Client", unexpected_client)
    result = ArticleRetriever().retrieve(article)

    assert result.evidence_retrieval_status == "feed_content"
    assert result.article_text.endswith("Read the full story on our website.")
    assert "completeness not verified" in FEED_CONTENT_LIMITATION
    assert "may be an excerpt" in FEED_CONTENT_LIMITATION

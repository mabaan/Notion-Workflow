from datetime import UTC, datetime

from research_automation.models.article import Article
from research_automation.models.source import Source
from research_automation.pipeline.collect import collect_articles
from research_automation.sources.rss import FeedHttpError, FeedParseError, FeedUnchanged
from research_automation.sources.rss import fetch_feed_bytes
import httpx


def _source(name, method="RSS"):
    return Source(
        name=name,
        source_type="Publisher",
        feed_url=f"https://{name}.example/rss",
        collection_method=method,
        check_frequency="Daily",
        notion_page_id=name,
    )


def test_collection_returns_structured_outcomes_and_deterministic_articles(monkeypatch) -> None:
    def collect(self):
        if self.source.name == "http":
            raise FeedHttpError("503")
        if self.source.name == "parse":
            raise FeedParseError("bad xml")
        if self.source.name == "unchanged":
            raise FeedUnchanged("304")
        if self.source.name == "empty":
            return []
        return [
            Article(
                title=f"Global energy story from {self.source.name}",
                url=f"https://{self.source.name}.example/story",
                canonical_url=f"https://{self.source.name}.example/story",
                source_name=self.source.name,
                source_page_id=self.source.notion_page_id,
                published_date=datetime(2026, 9, 1, tzinfo=UTC),
                publisher_key=self.source.notion_page_id,
            )
        ]

    monkeypatch.setattr("research_automation.pipeline.collect.RssSource.collect", collect)
    result = collect_articles(
        [
            _source("zulu"),
            _source("alpha"),
            _source("empty"),
            _source("unchanged"),
            _source("http"),
            _source("parse"),
            _source("api", "API"),
        ]
    )
    assert [article.source_name for article in result.articles] == ["alpha", "zulu"]
    assert {attempt.source_name: attempt.outcome for attempt in result.attempts} == {
        "alpha": "Success",
        "empty": "Empty",
        "http": "HTTP Error",
        "parse": "Parse Error",
        "unchanged": "Unchanged",
        "zulu": "Success",
    }
    assert result.skipped_sources == [
        "Skipped api: unsupported direct collection method API"
    ]


def test_feed_fetch_retries_transient_failures_at_most_twice(monkeypatch) -> None:
    request = httpx.Request("GET", "https://feed.example/rss")

    class FakeClient:
        def __init__(self, **kwargs):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            self.calls += 1
            status = 503 if self.calls < 3 else 200
            return httpx.Response(status, request=request, content=b"<rss/>")

    fake = FakeClient()
    monkeypatch.setattr(
        "research_automation.sources.rss.httpx.Client", lambda **kwargs: fake
    )
    assert fetch_feed_bytes("https://feed.example/rss") == b"<rss/>"
    assert fake.calls == 3

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json

from research_automation.models.article import Article
from research_automation.pipeline.article_classification import prepare_classification_inputs
from research_automation.utils.hashing import build_url_hash


NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


def article(key="story", **overrides):
    base = Article(
        "An ordinary editorial headline", f"https://publisher.example/{key}",
        f"https://publisher.example/{key}", "Publisher", "registered",
        published_date=NOW, snippet="An RSS description.", region=["UAE"],
        article_text="FULL ARTICLE MUST NEVER BE SENT TO THE CLASSIFIER",
    )
    return replace(base, **overrides)


def test_objective_preparation_keeps_topics_the_old_keyword_gate_would_reject():
    articles = [
        article("weather", title="Ordinary Saudi thunderstorm forecast"),
        article("politics", title="Unrelated political discussion continues"),
        article("science", title="Molecular clustering in water studied"),
        article("indirect", title="Hormuz delays threaten the harvest"),
    ]
    prepared = prepare_classification_inputs(articles, now=NOW)
    assert not prepared.excluded
    assert [record.title for record in prepared.inputs] == [item.title for item in articles]
    assert all(record.source_region_hints == ("UAE",) for record in prepared.inputs)
    payload = json.dumps([record.as_record() for record in prepared.inputs])
    assert "FULL ARTICLE" not in payload and "article_text" not in payload
    assert all(item.url_hash == "" and item.region == ["UAE"] for item in articles)


def test_only_invalid_stale_duplicate_processed_and_self_published_articles_are_excluded():
    articles = [
        article("valid"),
        article("alias", canonical_url="https://publisher.example/valid?utm_source=rss"),
        article("processed"),
        article("hash-processed"),
        article("invalid-url", canonical_url="ftp://publisher.example/story"),
        article("bad-port", canonical_url="https://publisher.example:not-a-port/story"),
        article("short", title="Short"),
        article("unknown-date", published_date=None),
        article("stale", published_date=NOW - timedelta(days=8)),
        article("self", canonical_url="https://news.somamater.com/story"),
        article("self-origin", url="https://somamater.com/story"),
    ]
    prepared = prepare_classification_inputs(
        articles, now=NOW,
        excluded_urls=["https://publisher.example/processed?utm_source=test"],
        seen_url_hashes=[build_url_hash("https://publisher.example/hash-processed")],
    )
    assert len(prepared.inputs) == 1 and len(prepared.excluded) == 10
    assert prepared.inputs[0].article_id == build_url_hash("https://publisher.example/valid")
    assert [excluded.reason for excluded in prepared.excluded] == [
        "duplicate or previously processed URL", "duplicate or previously processed URL",
        "duplicate or previously processed URL", "invalid URL", "invalid URL", "invalid title",
        "unknown or invalid publication date", "outside freshness window", "self-published content",
        "self-published content",
    ]


def test_freshness_boundary_and_naive_dates_follow_existing_utc_convention():
    boundary = NOW - timedelta(days=7)
    prepared = prepare_classification_inputs([
        article("boundary", published_date=boundary),
        article("naive", published_date=NOW.replace(tzinfo=None)),
        article("too-old", published_date=boundary - timedelta(seconds=1)),
    ], now=NOW)
    assert len(prepared.inputs) == 2
    assert prepared.excluded[0].reason == "outside freshness window"


def test_stable_ids_ignore_input_order_tracking_and_source_region_hints():
    first = article("one", canonical_url="https://publisher.example/one?utm_source=test")
    second = article("two")
    left = prepare_classification_inputs([first, second], now=NOW)
    right = prepare_classification_inputs([second, replace(first, region=["Global"])], now=NOW)
    assert {item.title + item.article_id for item in left.inputs} == {item.title + item.article_id for item in right.inputs}

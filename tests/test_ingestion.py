from datetime import UTC, datetime
from pathlib import Path

import pytest

import research_automation.pipeline.ingestion as ingestion_module
from research_automation.config import Settings
from research_automation.models.article import Article, EnrichedArticle
from research_automation.models.source import SourceAttempt
from research_automation.notion_schema import ARTICLE_QUEUE, SOURCE_REGISTRY_PROPERTY_TYPES
from research_automation.pipeline.collect import CollectionResult
from research_automation.pipeline.discovery import RequestBudget
from research_automation.pipeline.ingestion import (
    IngestionOptions,
    run_ingestion,
)


NOW = datetime(2026, 9, 1, 8, tzinfo=UTC)


@pytest.fixture(autouse=True)
def freeze_ingestion_time(monkeypatch) -> None:
    monkeypatch.setattr(ingestion_module, "utc_now", lambda: NOW)


class FakeNotion:
    def __init__(
        self,
        *,
        fail_article_create=False,
        article_pages=None,
        source_rows=None,
    ):
        self.fail_article_create = fail_article_create
        self.creates = []
        self.updates = []
        self.article_pages = article_pages or []
        self.source_rows = source_rows if source_rows is not None else [_source_row()]

    def retrieve_database(self, database_id):
        if database_id == "source-db":
            return {
                "properties": {
                    name: {"type": property_type}
                    for name, property_type in SOURCE_REGISTRY_PROPERTY_TYPES.items()
                }
            }
        return {"properties": {name: {"type": "unknown"} for name in ARTICLE_QUEUE.values()}}

    def query_database(
        self,
        database_id,
        page_size=100,
        filter_payload=None,
        sorts=None,
        max_results=None,
    ):
        if database_id == "source-db":
            return self.source_rows
        if database_id == "dataset-db":
            return [
                {
                    "id": "dataset-1",
                    "properties": {
                        "Newsletter": {"relation": [{"id": "newsletter-1"}]}
                    },
                }
            ]
        if database_id == "newsletter-db":
            return [
                {
                    "id": "newsletter-1",
                    "properties": {
                        "Dataset Source": {"relation": [{"id": "dataset-1"}]},
                        "Social Media Script": {"relation": [{"id": "social-1"}]},
                    },
                }
            ]
        if database_id == "social-db":
            return [
                {
                    "id": "social-1",
                    "properties": {
                        "Newsletter Source": {"relation": [{"id": "newsletter-1"}]},
                        "Dataset Source": {"relation": [{"id": "dataset-1"}]},
                    },
                }
            ]
        if database_id == "article-db":
            return self.article_pages
        raise AssertionError(database_id)

    def create_page(self, database_id, properties, children=None):
        self.creates.append((database_id, properties))
        if database_id == "article-db" and self.fail_article_create:
            raise RuntimeError("simulated Notion failure")
        return {"id": f"created-{len(self.creates)}", "properties": properties}

    def update_page(self, page_id, properties):
        self.updates.append((page_id, properties))
        return {"id": page_id, "properties": properties}


class FakeLlm:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def enrich_article(self, article):
        self.calls.append(article.title)
        if self.fail:
            raise RuntimeError("simulated enrichment failure")
        return EnrichedArticle(
            summary="Complete summary",
            why_it_matters="Material consequence",
            relevance_score=5,
            topic=["energy transition"],
            region=["Global"],
            newsletter_angle="Angle",
            sns_hook="Hook",
        )


class FakeDiscovery:
    def __init__(self, settings, sources):
        self.attempts = []
        self.budget = RequestBudget()

    def discover_articles(self, deficits, max_per_region, excluded_hashes):
        return []


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        notion_source_registry_database_id="source-db",
        notion_article_queue_database_id="article-db",
        notion_dataset_meetings_database_id="dataset-db",
        notion_newsletters_database_id="newsletter-db",
        notion_social_media_database_id="social-db",
        local_state_path=tmp_path,
        article_queue_weekly_target_global=1,
        article_queue_weekly_target_uae=1,
        article_queue_weekly_target_ksa=1,
        article_queue_weekly_target_egypt=1,
    )


def _source_row():
    return {
        "id": "publisher-1",
        "properties": {
            "Source Name": {"title": [{"plain_text": "Publisher One"}]},
            "Source Type": {"select": {"name": "Publisher"}},
            "Feed URL": {"url": "https://publisher.example/rss"},
            "Source URL": {"url": "https://publisher.example"},
            "Collection Method": {"select": {"name": "RSS"}},
            "Region": {"multi_select": [{"name": "Global"}]},
            "Topic Focus": {"multi_select": [{"name": "energy transition"}]},
            "Editorial Quality": {"number": 8},
            "Credibility": {"select": {"name": "High"}},
            "Acquisition Priority": {"select": {"name": "Core"}},
            "Check Frequency": {"select": {"name": "Daily"}},
            "Active": {"checkbox": True},
            "Last Attempt": {"date": None},
            "Last Success": {"date": None},
            "Last Outcome": {"select": None},
            "Last Error": {"rich_text": []},
            "Articles": {"relation": []},
        },
    }


def _collection(_sources):
    article = Article(
        title="Global solar grid investment accelerates",
        url="https://publisher.example/story",
        canonical_url="https://publisher.example/story",
        source_name="Publisher One",
        source_page_id="publisher-1",
        published_date=NOW,
        snippet="Global renewable energy grid policy and solar investment",
        region=["Global"],
        topic_focus=["energy transition"],
        source_editorial_quality=8,
        publisher_key="publisher-1",
    )
    return CollectionResult(
        articles=[article],
        attempts=[
            SourceAttempt(
                "publisher-1", "Publisher One", NOW, "Success", article_count=1
            )
        ],
    )


def test_ingestion_level_dry_run_evaluates_complete_path_without_writes(tmp_path) -> None:
    notion = FakeNotion()
    lines = []
    report = run_ingestion(
        _settings(tmp_path),
        IngestionOptions(dry_run=True),
        notion=notion,
        llm_client=FakeLlm(),
        collector=_collection,
        discovery_factory=FakeDiscovery,
        output=lines.append,
    )
    assert [winner.article.title for winner in report.selection.winners] == [
        "Global solar grid investment accelerates"
    ]
    assert notion.creates == []
    assert notion.updates == []
    assert not (tmp_path / "seen_articles.json").exists()
    assert "Notion writes: 0 (dry-run)" in lines
    assert any(line.startswith("Would create #1: region=Global") for line in lines)


def test_no_enrich_can_never_write_live(tmp_path) -> None:
    notion = FakeNotion()
    with pytest.raises(ValueError, match="requires --dry-run"):
        run_ingestion(
            _settings(tmp_path),
            IngestionOptions(no_enrich=True),
            notion=notion,
            collector=_collection,
            discovery_factory=FakeDiscovery,
        )
    assert notion.creates == []
    assert notion.updates == []


def test_enrichment_failure_creates_no_article_queue_page(tmp_path) -> None:
    notion = FakeNotion()
    report = run_ingestion(
        _settings(tmp_path),
        IngestionOptions(),
        notion=notion,
        llm_client=FakeLlm(fail=True),
        collector=_collection,
        discovery_factory=FakeDiscovery,
        output=lambda _: None,
    )
    assert report.pages_created == 0
    assert not any(database_id == "article-db" for database_id, _ in notion.creates)
    assert not (tmp_path / "seen_articles.json").exists()


def test_page_creation_failure_does_not_record_dedupe_or_replace_winner(tmp_path) -> None:
    notion = FakeNotion(fail_article_create=True)
    report = run_ingestion(
        _settings(tmp_path),
        IngestionOptions(),
        notion=notion,
        llm_client=FakeLlm(),
        collector=_collection,
        discovery_factory=FakeDiscovery,
        output=lambda _: None,
    )
    assert report.pages_created == 0
    assert len(report.page_errors) == 1
    assert report.selection.shortages["Global"] == 1
    assert not (tmp_path / "seen_articles.json").exists()


def test_successful_page_is_created_once_with_enrichment_in_initial_payload(tmp_path) -> None:
    notion = FakeNotion()
    report = run_ingestion(
        _settings(tmp_path),
        IngestionOptions(),
        notion=notion,
        llm_client=FakeLlm(),
        collector=_collection,
        discovery_factory=FakeDiscovery,
        output=lambda _: None,
    )
    article_creates = [props for database, props in notion.creates if database == "article-db"]
    assert report.pages_created == 1
    assert len(article_creates) == 1
    assert article_creates[0]["Summary"]["rich_text"][0]["text"]["content"] == "Complete summary"
    assert article_creates[0]["Processed"]["checkbox"] is True
    assert (tmp_path / "seen_articles.json").exists()


def test_dry_run_uses_existing_weekly_counts_and_stops_when_targets_are_full(tmp_path) -> None:
    pages = []
    for index, region in enumerate(("Global", "UAE", "KSA", "Egypt"), start=1):
        pages.append(
            {
                "properties": {
                    "TItle": {"title": [{"plain_text": f"Existing {region} story"}]},
                    "Region": {"multi_select": [{"name": region}]},
                    "Canonical URL": {"url": f"https://existing{index}.example/story"},
                    "URL": {"url": f"https://existing{index}.example/story"},
                    "Source": {"relation": [{"id": f"existing-publisher-{index}"}]},
                }
            }
        )
    notion = FakeNotion(article_pages=pages)
    llm = FakeLlm()
    report = run_ingestion(
        _settings(tmp_path),
        IngestionOptions(dry_run=True),
        notion=notion,
        llm_client=llm,
        collector=_collection,
        discovery_factory=FakeDiscovery,
        output=lambda _: None,
    )
    assert report.existing_region_counts == {
        "Global": 1,
        "UAE": 1,
        "KSA": 1,
        "Egypt": 1,
    }
    assert report.selection.winners == []
    assert llm.calls == []
    assert notion.creates == []
    assert notion.updates == []


def test_not_due_source_receives_no_health_write(tmp_path) -> None:
    row = _source_row()
    row["properties"]["Last Attempt"] = {
        "date": {"start": "2099-01-01T00:00:00Z"}
    }

    def empty_collection(sources):
        assert sources == []
        return CollectionResult()

    notion = FakeNotion(source_rows=[row])
    run_ingestion(
        _settings(tmp_path),
        IngestionOptions(),
        notion=notion,
        llm_client=FakeLlm(),
        collector=empty_collection,
        discovery_factory=FakeDiscovery,
        output=lambda _: None,
    )
    assert notion.updates == []


def test_discovery_widens_shortage_before_two_slot_expansion(tmp_path) -> None:
    feed_articles = [
        Article(
            title=f"Global renewable grid project{index} advances",
            url=f"https://publisher.example/feed-{index}",
            canonical_url=f"https://publisher.example/feed-{index}",
            source_name="Publisher One",
            source_page_id="publisher-1",
            published_date=NOW,
            snippet="Global renewable energy grid policy investment",
            region=["Global"],
            source_editorial_quality=8,
            publisher_key="publisher-1",
        )
        for index in range(7)
    ]

    def collection(_sources):
        return CollectionResult(articles=feed_articles)

    class ConditionalLlm:
        def __init__(self):
            self.calls = []

        def enrich_article(self, article):
            self.calls.append(article.title)
            score = 5 if article.discovery_provider else 1
            return EnrichedArticle(
                "summary",
                "why",
                score,
                topic=["energy transition"],
                region=["Global"],
            )

    class RecordingDiscovery:
        def __init__(self, settings, sources):
            self.called = False
            self.attempts = []
            self.budget = RequestBudget()

        def discover_articles(self, deficits, max_per_region, excluded_hashes):
            self.called = True
            self.budget.brave_requests = 1
            return [
                Article(
                    title="Global solar supply chain policy accelerates",
                    url="https://publisher-two.example/discovered",
                    canonical_url="https://publisher-two.example/discovered",
                    source_name="Publisher Two",
                    source_page_id="publisher-2",
                    published_date=NOW,
                    snippet="Global solar energy supply chain regulation",
                    region=["Global"],
                    source_editorial_quality=9,
                    publisher_key="publisher-2",
                    discovery_provider="Brave Search Fallback",
                )
            ]

    discovery_instances = []

    def discovery_factory(settings, sources):
        instance = RecordingDiscovery(settings, sources)
        discovery_instances.append(instance)
        return instance

    llm = ConditionalLlm()
    report = run_ingestion(
        _settings(tmp_path),
        IngestionOptions(dry_run=True),
        notion=FakeNotion(),
        llm_client=llm,
        collector=collection,
        discovery_factory=discovery_factory,
        output=lambda _: None,
    )
    assert discovery_instances[0].called is True
    assert len(llm.calls) == 8
    assert report.provider_requests["brave"] == 1
    assert [winner.article.discovery_provider for winner in report.selection.winners] == [
        "Brave Search Fallback"
    ]

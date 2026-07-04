from research_automation.clients.discovery_common import ProviderError
from research_automation.config import Settings
from research_automation.models.source import Source
from research_automation.pipeline.discovery import DiscoveryService
from research_automation.pipeline.source_registry import load_active_sources


class StubNotionClient:
    def __init__(self, rows):
        self.rows = rows

    def query_database(self, database_id, filter_payload=None):
        return self.rows


def _source_registry_row(name: str, collection_method: str, feed_url: str) -> dict:
    return {
        "id": f"{name}-id",
        "properties": {
            "Source Name": {
                "title": [{"plain_text": name}],
            },
            "Feed URL": {"url": feed_url or None},
            "Source URL": {"url": ""},
            "Collection Method": {"select": {"name": collection_method}},
            "Region": {"multi_select": []},
            "Topic Focus": {"multi_select": []},
            "Credibility": {"select": None},
            "Priority": {"select": None},
            "Check Frequency": {"select": None},
            "Active": {"checkbox": True},
        },
    }


def test_load_active_sources_keeps_api_rows_without_feed_url() -> None:
    notion = StubNotionClient(
        [
            _source_registry_row("Brave Search Fallback", "API", ""),
            _source_registry_row("Reuters", "RSS", "https://example.com/rss"),
        ]
    )
    settings = Settings(notion_source_registry_database_id="source-db")

    sources = load_active_sources(notion, settings)

    assert [source.name for source in sources] == [
        "Brave Search Fallback",
        "Reuters",
    ]
    assert sources[0].feed_url == ""


def test_discovery_service_prefers_active_api_rows_for_provider_order() -> None:
    settings = Settings(
        news_discovery_providers=("newsapi", "brave"),
    )
    sources = [
        Source(
            name="NewsAPI Fallback",
            feed_url="",
            collection_method="API",
            priority="Secondary",
        ),
        Source(
            name="Brave Search Fallback",
            feed_url="",
            collection_method="API",
            priority="Core",
        ),
    ]

    service = DiscoveryService(settings, sources)

    assert service.provider_order == ("brave", "newsapi")

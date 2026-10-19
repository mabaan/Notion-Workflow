from datetime import UTC, datetime

import pytest

from research_automation.config import Settings
from research_automation.notion_schema import SOURCE_REGISTRY_PROPERTY_TYPES
from research_automation.pipeline.source_registry import (
    SourceRegistryValidationError,
    load_active_sources,
)


class StubNotionClient:
    def __init__(self, rows, schema=None):
        self.rows = rows
        self.schema = schema or {
            name: {"type": property_type}
            for name, property_type in SOURCE_REGISTRY_PROPERTY_TYPES.items()
        }

    def retrieve_database(self, database_id):
        return {"properties": self.schema}

    def query_database(self, database_id, filter_payload=None):
        return self.rows


def _row(
    name: str,
    *,
    source_type: str = "Publisher",
    collection_method: str = "RSS",
    feed_url: str = "https://example.com/rss",
    quality=8,
    frequency: str = "Daily",
) -> dict:
    return {
        "id": f"{name}-id",
        "properties": {
            "Source Name": {"title": [{"plain_text": name}]},
            "Source Type": {"select": {"name": source_type}},
            "Feed URL": {"url": feed_url or None},
            "Source URL": {"url": "https://example.com"},
            "Collection Method": {"select": {"name": collection_method}},
            "Region": {"multi_select": [{"name": "Global"}]},
            "Topic Focus": {"multi_select": [{"name": "energy transition"}]},
            "Editorial Quality": {"number": quality},
            "Credibility": {"select": {"name": "High"}},
            "Acquisition Priority": {"select": {"name": "Core"}},
            "Check Frequency": {"select": {"name": frequency}},
            "Active": {"checkbox": True},
            "Last Attempt": {"date": {"start": "2026-08-31T08:00:00Z"}},
            "Last Success": {"date": {"start": "2026-08-30T08:00:00Z"}},
            "Last Outcome": {"select": {"name": "Success"}},
            "Last Error": {"rich_text": []},
            "Articles": {"relation": []},
        },
    }


def test_revised_registry_parses_typed_fields_and_ignores_notion_row_order() -> None:
    notion = StubNotionClient([_row("Zulu"), _row("Alpha")])
    sources = load_active_sources(
        notion, Settings(notion_source_registry_database_id="source-db")
    )
    assert [source.name for source in sources] == ["Alpha", "Zulu"]
    assert sources[0].source_type == "Publisher"
    assert sources[0].editorial_quality == 8
    assert sources[0].acquisition_priority == "Core"
    assert sources[0].last_attempt == datetime(2026, 8, 31, 8, tzinfo=UTC)
    assert sources[0].last_success == datetime(2026, 8, 30, 8, tzinfo=UTC)


@pytest.mark.parametrize("quality", [0, 11, "excellent", True])
def test_editorial_quality_outside_numeric_one_to_ten_fails(quality) -> None:
    notion = StubNotionClient([_row("Bad rating", quality=quality)])
    with pytest.raises(SourceRegistryValidationError, match="Editorial Quality"):
        load_active_sources(notion, Settings(notion_source_registry_database_id="db"))


def test_unrated_publisher_is_allowed_with_warning(caplog) -> None:
    notion = StubNotionClient([_row("Unrated", quality=None)])
    sources = load_active_sources(notion, Settings(notion_source_registry_database_id="db"))
    assert sources[0].editorial_quality is None
    assert "has no Editorial Quality" in caplog.text


def test_publisher_without_feed_is_rejected() -> None:
    notion = StubNotionClient([_row("Publisher", feed_url="")])
    with pytest.raises(SourceRegistryValidationError, match="requires a usable Feed URL"):
        load_active_sources(notion, Settings(notion_source_registry_database_id="db"))


def test_publisher_api_without_implemented_direct_adapter_is_rejected() -> None:
    notion = StubNotionClient(
        [_row("Publisher API", collection_method="API", feed_url="")]
    )
    with pytest.raises(SourceRegistryValidationError, match="unsupported publisher"):
        load_active_sources(notion, Settings(notion_source_registry_database_id="db"))


def test_discovery_provider_without_feed_is_accepted() -> None:
    notion = StubNotionClient(
        [
            _row(
                "Brave Search Fallback",
                source_type="Discovery Provider",
                collection_method="API",
                feed_url="",
                frequency="On Demand",
                quality=5,
            )
        ]
    )
    sources = load_active_sources(notion, Settings(notion_source_registry_database_id="db"))
    assert sources[0].source_type == "Discovery Provider"
    assert sources[0].feed_url == ""


def test_schema_validation_lists_incorrect_types() -> None:
    schema = {
        name: {"type": property_type}
        for name, property_type in SOURCE_REGISTRY_PROPERTY_TYPES.items()
    }
    schema["Last Attempt"] = {"type": "select"}
    schema["Last Success"] = {"type": "rich_text"}
    with pytest.raises(SourceRegistryValidationError) as raised:
        load_active_sources(
            StubNotionClient([], schema=schema),
            Settings(notion_source_registry_database_id="db"),
        )
    message = str(raised.value)
    assert "'Last Attempt' has type 'select'; expected 'date'" in message
    assert "'Last Success' has type 'rich_text'; expected 'date'" in message

from datetime import UTC, datetime, timedelta

from research_automation.models.source import Source, SourceAttempt
from research_automation.pipeline.source_health import (
    select_due_sources,
    update_source_health,
)


NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)


class FakeNotion:
    def __init__(self):
        self.updates = []

    def update_page(self, page_id, properties):
        self.updates.append((page_id, properties))


def _source(name, frequency, last_attempt=None, source_type="Publisher"):
    return Source(
        name=name,
        source_type=source_type,
        collection_method="RSS" if source_type == "Publisher" else "API",
        check_frequency=frequency,
        last_attempt=last_attempt,
        notion_page_id=name,
    )


def test_daily_and_weekly_due_boundaries_and_on_demand_exclusion() -> None:
    sources = [
        _source("daily-due", "Daily", NOW - timedelta(hours=24)),
        _source("daily-not-due", "Daily", NOW - timedelta(hours=23)),
        _source("weekly-due", "Weekly", NOW - timedelta(days=7)),
        _source("weekly-not-due", "Weekly", NOW - timedelta(days=6)),
        _source("never", "Daily"),
        _source("on-demand", "On Demand"),
        _source("provider", "On Demand", source_type="Discovery Provider"),
    ]
    assert [source.name for source in select_due_sources(sources, NOW)] == [
        "daily-due",
        "never",
        "weekly-due",
    ]


def test_all_sources_bypasses_publisher_frequency_but_not_provider_type() -> None:
    sources = [
        _source("on-demand", "On Demand"),
        _source("provider", "On Demand", source_type="Discovery Provider"),
    ]
    assert [source.name for source in select_due_sources(sources, NOW, all_sources=True)] == [
        "on-demand"
    ]


def test_success_updates_attempt_success_outcome_and_clears_error() -> None:
    notion = FakeNotion()
    update_source_health(
        notion,
        SourceAttempt("source", "Source", NOW, "Empty", article_count=0),
    )
    properties = notion.updates[0][1]
    assert properties["Last Attempt"]["date"]["start"] == NOW.isoformat()
    assert properties["Last Success"]["date"]["start"] == NOW.isoformat()
    assert properties["Last Outcome"]["select"]["name"] == "Empty"
    assert properties["Last Error"]["rich_text"] == []


def test_failure_updates_attempt_outcome_error_but_not_last_success() -> None:
    notion = FakeNotion()
    update_source_health(
        notion,
        SourceAttempt("source", "Source", NOW, "HTTP Error", error="timed out"),
    )
    properties = notion.updates[0][1]
    assert "Last Success" not in properties
    assert properties["Last Outcome"]["select"]["name"] == "HTTP Error"
    assert properties["Last Error"]["rich_text"][0]["text"]["content"] == "timed out"


def test_later_success_clears_previous_error() -> None:
    notion = FakeNotion()
    update_source_health(
        notion,
        SourceAttempt("source", "Source", NOW, "Parse Error", error="bad XML"),
    )
    update_source_health(
        notion,
        SourceAttempt("source", "Source", NOW + timedelta(hours=1), "Success"),
    )
    assert notion.updates[0][1]["Last Error"]["rich_text"]
    assert notion.updates[1][1]["Last Error"]["rich_text"] == []

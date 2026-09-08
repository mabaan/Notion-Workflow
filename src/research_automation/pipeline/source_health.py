"""Source due scheduling and Source Registry health updates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from research_automation.clients.notion_client import NotionClient
from research_automation.models.source import Source, SourceAttempt
from research_automation.notion_schema import SOURCE_REGISTRY
from research_automation.utils import notion_properties as props

SUCCESS_OUTCOMES = {"Success", "Unchanged", "Empty"}
FAILURE_OUTCOMES = {"Parse Error", "HTTP Error"}
SUPPORTED_OUTCOMES = SUCCESS_OUTCOMES | FAILURE_OUTCOMES


def select_due_sources(
    sources: list[Source],
    now: datetime,
    all_sources: bool = False,
) -> list[Source]:
    """Select due publishers; discovery providers are demand-triggered elsewhere."""

    current = _aware_utc(now)
    due: list[Source] = []
    for source in sources:
        if source.source_type != "Publisher":
            continue
        if all_sources:
            due.append(source)
            continue
        if source.check_frequency == "On Demand":
            continue
        interval = timedelta(days=1 if source.check_frequency == "Daily" else 7)
        if source.last_attempt is None or current - _aware_utc(source.last_attempt) >= interval:
            due.append(source)
    return sorted(due, key=lambda item: (item.name.casefold(), item.notion_page_id))


def update_source_health(notion: NotionClient, attempt: SourceAttempt) -> None:
    """Persist health only for a source that was actually contacted."""

    if attempt.outcome not in SUPPORTED_OUTCOMES:
        raise ValueError(f"Unsupported source outcome: {attempt.outcome}")

    values = {
        SOURCE_REGISTRY["last_attempt"]: props.date_value(attempt.attempted_at),
        SOURCE_REGISTRY["last_outcome"]: props.select(attempt.outcome),
        SOURCE_REGISTRY["last_error"]: props.rich_text(
            "" if attempt.outcome in SUCCESS_OUTCOMES else attempt.error[:1000]
        ),
    }
    if attempt.outcome in SUCCESS_OUTCOMES:
        values[SOURCE_REGISTRY["last_success"]] = props.date_value(
            attempt.attempted_at
        )
    notion.update_page(attempt.source_page_id, values)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

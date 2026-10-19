"""Validate, read, and normalize active sources from Notion."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from research_automation.clients.notion_client import NotionClient
from research_automation.config import Settings
from research_automation.models.source import Source
from research_automation.notion_schema import (
    SOURCE_REGISTRY,
    SOURCE_REGISTRY_PROPERTY_TYPES,
)
from research_automation.utils.dates import parse_iso_datetime

logger = logging.getLogger(__name__)

SOURCE_TYPES = {"Publisher", "Discovery Provider"}
CHECK_FREQUENCIES = {"Daily", "Weekly", "On Demand"}
DIRECT_FEED_METHODS = {"RSS", "Google News RSS", "Website"}


class SourceRegistryValidationError(ValueError):
    """The Source Registry schema or an active row is not operationally valid."""


def validate_source_registry_schema(
    notion: NotionClient,
    settings: Settings,
) -> None:
    """Fail before ingestion when required live properties are absent or mistyped."""

    database = notion.retrieve_database(settings.notion_source_registry_database_id)
    properties = database.get("properties", {})
    errors: list[str] = []
    for name, expected_type in SOURCE_REGISTRY_PROPERTY_TYPES.items():
        actual = properties.get(name)
        if actual is None:
            errors.append(f"missing {name!r} (expected {expected_type})")
            continue
        actual_type = actual.get("type", "unknown")
        if actual_type != expected_type:
            errors.append(
                f"{name!r} has type {actual_type!r}; expected {expected_type!r}"
            )

    if errors:
        details = "\n- ".join(errors)
        raise SourceRegistryValidationError(
            "Source Registry schema is incompatible with ingestion:\n- " + details
        )


def load_active_sources(notion: NotionClient, settings: Settings) -> list[Source]:
    """Return validated active Source Registry rows in deterministic order."""

    validate_source_registry_schema(notion, settings)
    rows = notion.query_database(
        settings.notion_source_registry_database_id,
        filter_payload={
            "property": SOURCE_REGISTRY["active"],
            "checkbox": {"equals": True},
        },
    )

    sources: list[Source] = []
    errors: list[str] = []
    for row in rows:
        try:
            sources.append(_parse_source(row))
        except SourceRegistryValidationError as exc:
            errors.append(str(exc))

    if errors:
        raise SourceRegistryValidationError(
            "Active Source Registry rows are invalid:\n- " + "\n- ".join(errors)
        )

    return sorted(sources, key=lambda source: (source.name.casefold(), source.notion_page_id))


def _parse_source(row: dict[str, Any]) -> Source:
    properties = row.get("properties", {})
    name = _title_text(properties.get(SOURCE_REGISTRY["title"], {})) or "Untitled"
    page_id = str(row.get("id") or "")
    context = f"{name!r} ({page_id or 'missing page id'})"

    source_type = _select_name(properties.get(SOURCE_REGISTRY["source_type"], {}))
    if source_type not in SOURCE_TYPES:
        raise SourceRegistryValidationError(
            f"{context}: Source Type must be Publisher or Discovery Provider"
        )

    editorial_quality = properties.get(
        SOURCE_REGISTRY["editorial_quality"], {}
    ).get("number")
    if editorial_quality is not None:
        if isinstance(editorial_quality, bool) or not isinstance(
            editorial_quality, (int, float)
        ):
            raise SourceRegistryValidationError(
                f"{context}: Editorial Quality must be a number from 1 through 10"
            )
        editorial_quality = float(editorial_quality)
        if not 1 <= editorial_quality <= 10:
            raise SourceRegistryValidationError(
                f"{context}: Editorial Quality {editorial_quality:g} is outside 1 through 10"
            )
    elif source_type == "Publisher":
        logger.warning("Publisher %s has no Editorial Quality rating.", name)

    collection_method = _select_name(
        properties.get(SOURCE_REGISTRY["collection_method"], {})
    )
    feed_url = properties.get(SOURCE_REGISTRY["feed_url"], {}).get("url") or ""
    check_frequency = _select_name(
        properties.get(SOURCE_REGISTRY["check_frequency"], {})
    )
    if source_type == "Publisher":
        if check_frequency not in CHECK_FREQUENCIES:
            raise SourceRegistryValidationError(
                f"{context}: Check Frequency must be Daily, Weekly, or On Demand"
            )
        if collection_method not in DIRECT_FEED_METHODS:
            raise SourceRegistryValidationError(
                f"{context}: unsupported publisher Collection Method {collection_method!r}"
            )
        if not feed_url:
            raise SourceRegistryValidationError(
                f"{context}: Publisher using {collection_method} requires a usable Feed URL"
            )

    return Source(
        name=name,
        feed_url=feed_url,
        source_url=properties.get(SOURCE_REGISTRY["source_url"], {}).get("url") or "",
        source_type=source_type,
        collection_method=collection_method,
        region=_multi_select_names(properties.get(SOURCE_REGISTRY["region"], {})),
        topic_focus=_multi_select_names(
            properties.get(SOURCE_REGISTRY["topic_focus"], {})
        ),
        editorial_quality=editorial_quality,
        credibility=_select_name(properties.get(SOURCE_REGISTRY["credibility"], {})),
        acquisition_priority=_select_name(
            properties.get(SOURCE_REGISTRY["acquisition_priority"], {})
        ),
        check_frequency=check_frequency,
        last_attempt=_date_value(
            properties.get(SOURCE_REGISTRY["last_attempt"], {}),
            context=context,
            field_name=SOURCE_REGISTRY["last_attempt"],
        ),
        last_success=_date_value(
            properties.get(SOURCE_REGISTRY["last_success"], {}),
            context=context,
            field_name=SOURCE_REGISTRY["last_success"],
        ),
        notion_page_id=page_id,
    )


def _title_text(property_value: dict[str, Any]) -> str:
    return "".join(
        item.get("plain_text", "") for item in property_value.get("title", [])
    ).strip()


def _select_name(property_value: dict[str, Any]) -> str:
    return (property_value.get("select") or {}).get("name", "")


def _multi_select_names(property_value: dict[str, Any]) -> list[str]:
    return [
        option.get("name", "")
        for option in property_value.get("multi_select", [])
        if option.get("name")
    ]


def _date_value(
    property_value: dict[str, Any],
    *,
    context: str,
    field_name: str,
) -> datetime | None:
    raw = (property_value.get("date") or {}).get("start")
    if not raw:
        return None
    try:
        return parse_iso_datetime(str(raw))
    except ValueError as exc:
        raise SourceRegistryValidationError(
            f"{context}: {field_name} contains invalid Notion date value {raw!r}"
        ) from exc

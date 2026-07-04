"""Read and normalize active sources from Notion."""

from __future__ import annotations

import logging
from typing import Any

from research_automation.clients.notion_client import NotionClient
from research_automation.config import Settings
from research_automation.models.source import Source
from research_automation.notion_schema import SOURCE_REGISTRY

logger = logging.getLogger(__name__)


def load_active_sources(notion: NotionClient, settings: Settings) -> list[Source]:
    """Return active Source Registry rows as Source models."""

    rows = notion.query_database(
        settings.notion_source_registry_database_id,
        filter_payload={
            "property": SOURCE_REGISTRY["active"],
            "checkbox": {"equals": True},
        },
    )

    sources: list[Source] = []
    for row in rows:
        properties = row.get("properties", {})
        feed_url = properties.get(SOURCE_REGISTRY["feed_url"], {}).get("url") or ""
        name = _title_text(properties.get(SOURCE_REGISTRY["title"], {})) or "Untitled"
        collection_method = _select_name(
            properties.get(SOURCE_REGISTRY["collection_method"], {})
        )

        if not feed_url and collection_method != "API":
            logger.warning("Skipping source without Feed URL: %s", name)
            continue

        sources.append(
            Source(
                name=name,
                feed_url=feed_url,
                source_url=properties.get(SOURCE_REGISTRY["source_url"], {}).get("url")
                or "",
                collection_method=collection_method,
                region=_multi_select_names(properties.get(SOURCE_REGISTRY["region"], {})),
                topic_focus=_multi_select_names(
                    properties.get(SOURCE_REGISTRY["topic_focus"], {})
                ),
                credibility=_select_name(
                    properties.get(SOURCE_REGISTRY["credibility"], {})
                ),
                priority=_select_name(properties.get(SOURCE_REGISTRY["priority"], {})),
                check_frequency=_select_name(
                    properties.get(SOURCE_REGISTRY["check_frequency"], {})
                ),
                notion_page_id=row.get("id", ""),
            )
        )

    return sources


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

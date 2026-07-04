"""Weekly draft generation helpers."""

from __future__ import annotations

from typing import Any

from research_automation.clients.notion_client import NotionClient
from research_automation.config import Settings
from research_automation.models.draft import DraftArticle
from research_automation.notion_schema import ARTICLE_QUEUE, SOURCE_REGISTRY


def load_weekly_draft_articles(
    notion: NotionClient,
    settings: Settings,
    dataset_meeting_page_id: str,
    statuses: list[str],
) -> list[DraftArticle]:
    """Load approved Article Queue rows for weekly drafting."""

    filters: list[dict[str, Any]] = [
        {
            "property": ARTICLE_QUEUE["dataset_meeting"],
            "relation": {"contains": dataset_meeting_page_id},
        }
    ]

    if len(statuses) == 1:
        filters.append(
            {
                "property": ARTICLE_QUEUE["status"],
                "select": {"equals": statuses[0]},
            }
        )
    else:
        filters.append(
            {
                "or": [
                    {
                        "property": ARTICLE_QUEUE["status"],
                        "select": {"equals": status},
                    }
                    for status in statuses
                ]
            }
        )

    pages = notion.query_database(
        settings.notion_article_queue_database_id,
        filter_payload={"and": filters},
    )
    source_cache: dict[str, str] = {}
    return [_page_to_draft_article(notion, source_cache, page) for page in pages]


def format_articles_for_prompt(articles: list[DraftArticle]) -> str:
    """Serialize article context into prompt-friendly text."""

    lines: list[str] = []
    for index, article in enumerate(articles, start=1):
        lines.extend(
            [
                f"{index}. Title: {article.title}",
                f"Source: {article.source_name}",
                f"URL: {article.canonical_url}",
                f"Summary: {article.summary or 'No summary available.'}",
                f"Why it matters: {article.why_it_matters or 'Not provided.'}",
                f"Newsletter angle: {article.newsletter_angle or 'Not provided.'}",
                f"SNS hook: {article.sns_hook or 'Not provided.'}",
                f"Topic: {', '.join(article.topic) or 'Unknown'}",
                f"Region: {', '.join(article.region) or 'Unknown'}",
                f"Relevance score: {article.relevance_score or 0}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _page_to_draft_article(
    notion: NotionClient,
    source_cache: dict[str, str],
    page: dict[str, Any],
) -> DraftArticle:
    properties = page.get("properties", {})
    relation_items = properties.get(ARTICLE_QUEUE["source"], {}).get("relation", [])
    source_page_id = relation_items[0]["id"] if relation_items else ""

    return DraftArticle(
        title=_title_text(properties.get(ARTICLE_QUEUE["title"], {})) or "Untitled",
        source_name=_source_name(notion, source_cache, source_page_id),
        canonical_url=properties.get(ARTICLE_QUEUE["canonical_url"], {}).get("url")
        or "",
        summary=_rich_text(properties.get(ARTICLE_QUEUE["summary"], {})),
        why_it_matters=_rich_text(properties.get(ARTICLE_QUEUE["why_it_matters"], {})),
        newsletter_angle=_rich_text(
            properties.get(ARTICLE_QUEUE["newsletter_angle"], {})
        ),
        sns_hook=_rich_text(properties.get(ARTICLE_QUEUE["sns_hook"], {})),
        topic=_multi_select(properties.get(ARTICLE_QUEUE["topic"], {})),
        region=_multi_select(properties.get(ARTICLE_QUEUE["region"], {})),
        relevance_score=_number(properties.get(ARTICLE_QUEUE["relevance_score"], {})),
    )


def select_featured_articles(
    articles: list[DraftArticle],
    *,
    max_items: int = 3,
) -> list[DraftArticle]:
    """Return the highest-priority articles for drafting."""

    ranked = sorted(
        articles,
        key=lambda article: (-article.relevance_score, article.title.casefold()),
    )
    return ranked[:max_items]


def _source_name(
    notion: NotionClient,
    cache: dict[str, str],
    page_id: str,
) -> str:
    if not page_id:
        return "Unknown source"
    if page_id in cache:
        return cache[page_id]

    page = notion.retrieve_page(page_id)
    properties = page.get("properties", {})
    name = _title_text(properties.get(SOURCE_REGISTRY["title"], {})) or "Unknown source"
    cache[page_id] = name
    return name


def _title_text(property_value: dict[str, Any]) -> str:
    return "".join(
        item.get("plain_text", "") for item in property_value.get("title", [])
    ).strip()


def _rich_text(property_value: dict[str, Any]) -> str:
    return "".join(
        item.get("plain_text", "") for item in property_value.get("rich_text", [])
    ).strip()


def _multi_select(property_value: dict[str, Any]) -> list[str]:
    return [
        item.get("name", "")
        for item in property_value.get("multi_select", [])
        if item.get("name")
    ]


def _number(property_value: dict[str, Any]) -> int:
    value = property_value.get("number")
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

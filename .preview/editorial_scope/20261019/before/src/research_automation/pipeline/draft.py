"""Weekly draft generation helpers."""

from __future__ import annotations

import logging
from typing import Any

from research_automation.clients.notion_client import NotionClient
from research_automation.config import Settings
from research_automation.models.draft import DraftArticle
from research_automation.notion_schema import ARTICLE_QUEUE, SOURCE_REGISTRY
from research_automation.utils.evidence import (
    FEED_CONTENT_LIMITATION,
    has_article_evidence,
    is_feed_content,
)
from research_automation.utils.urls import clean_url, url_hostname

logger = logging.getLogger(__name__)


def load_weekly_draft_articles(
    notion: NotionClient,
    settings: Settings,
    dataset_meeting_page_id: str,
    statuses: list[str],
    *,
    include_research_notes: bool = True,
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
    return [
        _page_to_draft_article(
            notion,
            source_cache,
            page,
            include_research_notes=include_research_notes,
        )
        for page in pages
    ]


def format_articles_for_prompt(articles: list[DraftArticle]) -> str:
    """Serialize the legacy article context for backward compatibility."""

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


def format_newsletter_articles_for_prompt(articles: list[DraftArticle]) -> str:
    """Serialize approved articles with bounded research evidence for newsletters."""

    records: list[str] = []
    for index, article in enumerate(articles, start=1):
        source_url = article.resolved_publisher_url or article.canonical_url
        status = article.evidence_retrieval_status or "Not available (legacy entry)"
        evidence_available = (
            has_article_evidence(article.evidence_retrieval_status)
            and bool(article.factual_points)
        )
        lines = [
            f"ARTICLE {index} - REFERENCE DATA",
            f"Title: {article.title}",
            f"Publisher: {article.source_name}",
            f"Canonical source URL: {source_url or 'Not available'}",
            f"Summary context: {article.summary or 'No summary available.'}",
            f"Why it matters context: {article.why_it_matters or 'Not provided.'}",
            f"Newsletter angle: {article.newsletter_angle or 'Not provided.'}",
            f"Research retrieval status: {status}",
            f"Topic: {', '.join(article.topic) or 'Unknown'}",
            f"Region: {', '.join(article.region) or 'Unknown'}",
        ]
        if evidence_available:
            if is_feed_content(status):
                lines.append(FEED_CONTENT_LIMITATION)
            lines.append("Factual evidence (primary reporting basis):")
            lines.extend(f"- {point}" for point in article.factual_points)
        else:
            lines.append(
                "Factual evidence: Full-article evidence is unavailable or incomplete. "
                "Use the summary context cautiously and do not add unsupported detail."
            )
            if article.factual_points:
                lines.append("Limited points from available feed context:")
                lines.extend(f"- {point}" for point in article.factual_points)
        lines.append("END ARTICLE REFERENCE DATA")
        records.append("\n".join(lines))
    return "\n\n".join(records)


def format_social_articles_for_prompt(articles: list[DraftArticle]) -> str:
    """Serialize approved articles with bounded research evidence for SNS."""

    records: list[str] = []
    for index, article in enumerate(articles, start=1):
        source_url = article.resolved_publisher_url or article.canonical_url
        status = article.evidence_retrieval_status or "Not available (legacy entry)"
        evidence_available = (
            has_article_evidence(article.evidence_retrieval_status)
            and bool(article.factual_points)
        )
        lines = [
            f"SOCIAL ARTICLE {index} - REFERENCE DATA",
            f"Title: {article.title}",
            f"Publisher: {article.source_name}",
            f"Publisher source URL: {source_url or 'Not available'}",
            f"Summary context: {article.summary or 'No summary available.'}",
            f"SNS hook context: {article.sns_hook or 'Not provided.'}",
            f"Research retrieval status: {status}",
            f"Topic: {', '.join(article.topic) or 'Unknown'}",
            f"Region: {', '.join(article.region) or 'Unknown'}",
        ]
        if evidence_available:
            if is_feed_content(status):
                lines.append(FEED_CONTENT_LIMITATION)
            lines.append("Factual evidence (primary script basis):")
            lines.extend(f"- {point}" for point in article.factual_points)
        else:
            lines.append(
                "Factual evidence: Full-article evidence is unavailable or incomplete. "
                "Use the summary and hook cautiously and do not add unsupported detail."
            )
            if article.factual_points:
                lines.append("Limited points from available feed context:")
                lines.extend(f"- {point}" for point in article.factual_points)
        lines.append("END SOCIAL ARTICLE REFERENCE DATA")
        records.append("\n".join(lines))
    return "\n\n".join(records)


def _page_to_draft_article(
    notion: NotionClient,
    source_cache: dict[str, str],
    page: dict[str, Any],
    *,
    include_research_notes: bool,
) -> DraftArticle:
    properties = page.get("properties", {})
    relation_items = properties.get(ARTICLE_QUEUE["source"], {}).get("relation", [])
    source_page_id = relation_items[0]["id"] if relation_items else ""
    research_notes = (
        _load_research_notes(notion, str(page.get("id") or ""))
        if include_research_notes
        else _empty_research_notes()
    )

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
        factual_points=research_notes["factual_points"],
        evidence_retrieval_status=research_notes["evidence_retrieval_status"],
        resolved_publisher_url=research_notes["resolved_publisher_url"],
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


def _load_research_notes(
    notion: NotionClient,
    page_id: str,
) -> dict[str, Any]:
    notes = _empty_research_notes()
    if not page_id:
        return notes
    try:
        blocks = notion.list_block_children(page_id)
    except Exception as exc:
        logger.warning(
            "Could not load Research Notes for Article Queue page %s: %s",
            page_id,
            exc,
        )
        return notes

    in_research_notes = False
    in_factual_points = False
    for block in blocks:
        block_type = str(block.get("type") or "")
        text = _block_text(block)
        if block_type == "heading_2":
            if text == "Research Notes":
                in_research_notes = True
                in_factual_points = False
                continue
            if in_research_notes:
                break
        if not in_research_notes:
            continue
        if block_type == "heading_1":
            break
        if block_type == "heading_3":
            in_factual_points = text == "Key Factual Points"
            continue
        if block_type == "paragraph":
            if text.startswith("Resolved publisher URL:"):
                candidate = _safe_http_url(text.partition(":")[2].strip())
                if candidate:
                    notes["resolved_publisher_url"] = candidate
            elif text.startswith("Evidence retrieval status:"):
                notes["evidence_retrieval_status"] = text.partition(":")[2].strip()
            continue
        if block_type == "bulleted_list_item" and in_factual_points and text:
            notes["factual_points"].append(text[:1800])

    notes["factual_points"] = notes["factual_points"][:8]
    return notes


def _empty_research_notes() -> dict[str, Any]:
    return {
        "factual_points": [],
        "evidence_retrieval_status": "",
        "resolved_publisher_url": "",
    }


def _safe_http_url(raw_url: str) -> str:
    if not raw_url.casefold().startswith(("http://", "https://")):
        return ""
    candidate = clean_url(raw_url)
    hostname = url_hostname(candidate)
    if not hostname or "." not in hostname or any(char.isspace() for char in candidate):
        return ""
    return candidate


def _block_text(block: dict[str, Any]) -> str:
    block_type = str(block.get("type") or "")
    rich_text = block.get(block_type, {}).get("rich_text", [])
    return "".join(
        str(item.get("plain_text") or item.get("text", {}).get("content") or "")
        for item in rich_text
    ).strip()

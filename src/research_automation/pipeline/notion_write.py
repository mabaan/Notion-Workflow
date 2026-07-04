"""Write helpers for the live Notion workflow."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from research_automation.clients.notion_client import NotionClient
from research_automation.models.article import Article, EnrichedArticle
from research_automation.notion_schema import (
    ARTICLE_QUEUE,
    DATASET_MEETINGS,
    NEWSLETTERS,
    SOCIAL_MEDIA,
    SOURCE_REGISTRY,
    NEWSLETTER_STATUS_IN_PROGRESS,
    SOCIAL_REVIEWED_NOT_YET,
    SOCIAL_STATUS_READY,
)
from research_automation.utils import notion_properties as props
from research_automation.pipeline.images import markdown_image_match
from research_automation.utils.regions import merge_region_labels


def create_article_queue_page(
    notion: NotionClient,
    database_id: str,
    article: Article,
    dataset_meeting_page_id: str | None,
) -> dict[str, Any]:
    """Create an Article Queue page from a collected article."""

    relation_ids = [article.source_page_id] if article.source_page_id else []
    dataset_relation_ids = [dataset_meeting_page_id] if dataset_meeting_page_id else []

    return notion.create_page(
        database_id=database_id,
        properties={
            ARTICLE_QUEUE["title"]: props.title(article.title),
            ARTICLE_QUEUE["url"]: props.url(article.url),
            ARTICLE_QUEUE["canonical_url"]: props.url(article.canonical_url),
            ARTICLE_QUEUE["source"]: props.relation(relation_ids),
            ARTICLE_QUEUE["published_date"]: props.date_value(article.published_date),
            ARTICLE_QUEUE["collected_date"]: props.date_value(article.collected_date),
            ARTICLE_QUEUE["dataset_meeting"]: props.relation(dataset_relation_ids),
            ARTICLE_QUEUE["topic"]: props.multi_select(article.topic_focus),
            ARTICLE_QUEUE["region"]: props.multi_select(article.region),
            ARTICLE_QUEUE["status"]: props.select("New"),
            ARTICLE_QUEUE["processed"]: props.checkbox(False),
            ARTICLE_QUEUE["duplicate"]: props.checkbox(False),
            ARTICLE_QUEUE["url_hash"]: props.rich_text(article.url_hash),
            ARTICLE_QUEUE["content_hash"]: props.rich_text(article.content_hash),
        },
    )


def update_article_enrichment(
    notion: NotionClient,
    page_id: str,
    enriched: EnrichedArticle,
    processed_at: datetime,
    *,
    base_regions: list[str] | None = None,
) -> None:
    """Update an Article Queue page with enrichment output."""

    notion.update_page(
        page_id,
        {
            ARTICLE_QUEUE["summary"]: props.rich_text(enriched.summary),
            ARTICLE_QUEUE["why_it_matters"]: props.rich_text(enriched.why_it_matters),
            ARTICLE_QUEUE["relevance_score"]: props.number(enriched.relevance_score),
            ARTICLE_QUEUE["newsletter_angle"]: props.rich_text(
                enriched.newsletter_angle
            ),
            ARTICLE_QUEUE["sns_hook"]: props.rich_text(enriched.sns_hook),
            ARTICLE_QUEUE["topic"]: props.multi_select(enriched.topic),
            ARTICLE_QUEUE["region"]: props.multi_select(
                merge_region_labels(base_regions or [], enriched.region)
            ),
            ARTICLE_QUEUE["processed"]: props.checkbox(True),
            ARTICLE_QUEUE["last_processed"]: props.date_value(processed_at),
            ARTICLE_QUEUE["error_notes"]: props.rich_text(""),
        },
    )


def update_article_error(
    notion: NotionClient,
    page_id: str,
    error_message: str,
) -> None:
    """Record an enrichment error on an article page."""

    notion.update_page(
        page_id,
        {
            ARTICLE_QUEUE["processed"]: props.checkbox(False),
            ARTICLE_QUEUE["error_notes"]: props.rich_text(error_message),
        },
    )


def update_source_last_checked(
    notion: NotionClient,
    page_id: str,
    checked_at_iso: str,
) -> None:
    """Update the live Source Registry Last Checked rich text field."""

    notion.update_page(
        page_id,
        {
            SOURCE_REGISTRY["last_checked"]: props.rich_text(checked_at_iso),
        },
    )


def ensure_relation_contains(
    notion: NotionClient,
    page: dict[str, Any],
    property_name: str,
    target_page_ids: Iterable[str],
) -> None:
    """Ensure a relation property contains the requested page IDs."""

    existing_ids = relation_ids(page, property_name)
    merged_ids = list(dict.fromkeys([*existing_ids, *target_page_ids]))
    if merged_ids == existing_ids:
        return
    notion.update_page(page["id"], {property_name: props.relation(merged_ids)})


def relation_ids(page: dict[str, Any], property_name: str) -> list[str]:
    """Return relation page IDs from a page property."""

    relation_items = page.get("properties", {}).get(property_name, {}).get("relation", [])
    return [item.get("id", "") for item in relation_items if item.get("id")]


def mark_newsletter_ready_for_review(
    notion: NotionClient,
    newsletter_page_id: str,
) -> None:
    """Update newsletter status after generating a draft."""

    notion.update_page(
        newsletter_page_id,
        {
            NEWSLETTERS["status"]: props.status(NEWSLETTER_STATUS_IN_PROGRESS),
        },
    )


def mark_social_media_ready(
    notion: NotionClient,
    social_media_page_id: str,
) -> None:
    """Update social page statuses after generating a draft."""

    notion.update_page(
        social_media_page_id,
        {
            SOCIAL_MEDIA["content_status"]: props.status(SOCIAL_STATUS_READY),
            SOCIAL_MEDIA["reviewed"]: props.status(SOCIAL_REVIEWED_NOT_YET),
        },
    )


def replace_generated_section(
    notion: NotionClient,
    page_id: str,
    marker_name: str,
    content: str,
) -> None:
    """Replace one automation-managed top-level section on a Notion page."""

    start_marker = f"[AUTOMATION:{marker_name}:start]"
    end_marker = f"[AUTOMATION:{marker_name}:end]"

    existing_blocks = notion.list_block_children(page_id)
    delete_ids = _section_block_ids(existing_blocks, start_marker, end_marker)

    for block_id in reversed(delete_ids):
        notion.delete_block(block_id)

    children = [_paragraph_block(start_marker)]
    children.extend(_markdown_blocks(content))
    children.append(_paragraph_block(end_marker))
    notion.append_block_children(page_id, children)


def _section_block_ids(
    blocks: list[dict[str, Any]],
    start_marker: str,
    end_marker: str,
) -> list[str]:
    in_section = False
    collected: list[str] = []

    for block in blocks:
        plain_text = _block_plain_text(block)
        if plain_text == start_marker:
            in_section = True
            collected.append(block["id"])
            continue

        if in_section:
            collected.append(block["id"])
            if plain_text == end_marker:
                break

    return collected


def _markdown_blocks(content: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in {"---", "***", "___"}:
            continue
        image = markdown_image_match(line)
        if image is not None:
            alt, url = image
            blocks.append(_image_block(url, alt))
            continue
        if line.startswith("### "):
            blocks.append(_rich_text_block("heading_3", line[4:]))
        elif line.startswith("## "):
            blocks.append(_rich_text_block("heading_2", line[3:]))
        elif line.startswith("# "):
            blocks.append(_rich_text_block("heading_1", line[2:]))
        elif line.startswith("- "):
            blocks.append(_rich_text_block("bulleted_list_item", line[2:]))
        elif _is_numbered_list_item(line):
            blocks.append(_rich_text_block("numbered_list_item", line.split(". ", 1)[1]))
        else:
            blocks.append(_paragraph_block(line))
    return blocks


def _is_numbered_list_item(line: str) -> bool:
    number, dot, remainder = line.partition(". ")
    return bool(number.isdigit() and dot and remainder)


def _paragraph_block(text: str) -> dict[str, Any]:
    return _rich_text_block("paragraph", text)


def _image_block(url: str, caption: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": url},
            "caption": props.rich_text_items(caption) if caption else [],
        },
    }


def _rich_text_block(block_type: str, text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": props.rich_text_items(text),
        },
    }


def _block_plain_text(block: dict[str, Any]) -> str:
    block_type = block.get("type", "")
    data = block.get(block_type, {})
    rich_text = data.get("rich_text", [])
    return "".join(item.get("plain_text", "") for item in rich_text).strip()

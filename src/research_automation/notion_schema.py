"""Live Notion schema constants for the local workflow."""

from __future__ import annotations

DATABASE_ID_FIELDS = {
    "source_registry": "notion_source_registry_database_id",
    "article_queue": "notion_article_queue_database_id",
    "dataset_meetings": "notion_dataset_meetings_database_id",
    "newsletters": "notion_newsletters_database_id",
    "social_media": "notion_social_media_database_id",
}

SOURCE_REGISTRY = {
    "title": "Source Name",
    "source_type": "Source Type",
    "feed_url": "Feed URL",
    "source_url": "Source URL",
    "collection_method": "Collection Method",
    "region": "Region",
    "topic_focus": "Topic Focus",
    "editorial_quality": "Editorial Quality",
    "credibility": "Credibility",
    "acquisition_priority": "Acquisition Priority",
    "check_frequency": "Check Frequency",
    "active": "Active",
    "last_attempt": "Last Attempt",
    "last_success": "Last Success",
    "last_outcome": "Last Outcome",
    "last_error": "Last Error",
    "articles": "Articles",
}

SOURCE_REGISTRY_PROPERTY_TYPES = {
    SOURCE_REGISTRY["title"]: "title",
    SOURCE_REGISTRY["source_type"]: "select",
    SOURCE_REGISTRY["active"]: "checkbox",
    SOURCE_REGISTRY["editorial_quality"]: "number",
    SOURCE_REGISTRY["acquisition_priority"]: "select",
    SOURCE_REGISTRY["credibility"]: "select",
    SOURCE_REGISTRY["check_frequency"]: "select",
    SOURCE_REGISTRY["collection_method"]: "select",
    SOURCE_REGISTRY["feed_url"]: "url",
    SOURCE_REGISTRY["source_url"]: "url",
    SOURCE_REGISTRY["region"]: "multi_select",
    SOURCE_REGISTRY["topic_focus"]: "multi_select",
    SOURCE_REGISTRY["last_attempt"]: "date",
    SOURCE_REGISTRY["last_success"]: "date",
    SOURCE_REGISTRY["last_outcome"]: "select",
    SOURCE_REGISTRY["last_error"]: "rich_text",
    SOURCE_REGISTRY["articles"]: "relation",
}

ARTICLE_QUEUE = {
    "title": "TItle",
    "url": "URL",
    "canonical_url": "Canonical URL",
    "source": "Source",
    "published_date": "Published Date",
    "collected_date": "Collected Date",
    "dataset_meeting": "Dataset Meeting",
    "newsletter": "Newsletter",
    "social_media_content": "Social Media Content",
    "topic": "Topic",
    "region": "Region",
    "summary": "Summary",
    "why_it_matters": "Why It Matters",
    "relevance_score": "Relevance  Score",
    "newsletter_angle": "Newsletter Angle",
    "sns_hook": "SNS Hook",
    "status": "Status",
    "processed": "Processed",
    "duplicate": "Duplicate",
    "url_hash": "URL Hash",
    "content_hash": "Content Hash",
    "error_notes": "Error Notes",
    "last_processed": "Last Processed",
    "queue_score": "Queue Score",
    "selection_reason": "Selection Reason",
}

DATASET_MEETINGS = {
    "title": "Name",
    "topics_addressed": "Topics Addressed",
    "date_presented": "Date Presented",
    "year": "Year",
    "newsletter": "Newsletter",
    "week_start": "Week Start",
    "week_end": "Week End",
    "status": "Status",
}

NEWSLETTERS = {
    "code": "Code #",
    "title": "Week",
    "status": "Status",
    "publish_date": "Date To Be Published",
    "social_media_script": "Social Media Script",
    "dataset_source": "Dataset Source",
}

SOCIAL_MEDIA = {
    "title": "Week",
    "content_status": "Content Status",
    "reviewed": "Reviewed",
    "newsletter_source": "Newsletter Source",
    "week_start": "Week Start",
    "week_end": "Week End",
    "dataset_source": "Dataset Source",
}

ARTICLE_QUEUE_DEFAULT_STATUS = "New"
DATASET_STATUS_NOT_STARTED = "Not started"
DATASET_STATUS_IN_PROGRESS = "In progress"
NEWSLETTER_STATUS_NOT_STARTED = "Not started"
NEWSLETTER_STATUS_IN_PROGRESS = "In progress"
SOCIAL_STATUS_NOT_READY = "Not ready"
SOCIAL_STATUS_READY = "Ready"
SOCIAL_REVIEWED_NOT_YET = "Not yet"

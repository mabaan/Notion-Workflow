"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Runtime settings for local scripts and deployed handlers."""

    notion_token: str = ""

    notion_source_registry_database_id: str = ""
    notion_article_queue_database_id: str = ""
    notion_dataset_meetings_database_id: str = ""
    notion_newsletters_database_id: str = ""
    notion_social_media_database_id: str = ""

    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: str = ""

    aws_region: str = "me-central-1"
    dynamodb_table_name: str = ""
    s3_bucket_name: str = ""

    log_level: str = "INFO"


def load_settings() -> Settings:
    """Load settings from .env and process environment."""

    load_dotenv()

    return Settings(
        notion_token=os.getenv("NOTION_TOKEN", ""),
        notion_source_registry_database_id=os.getenv(
            "NOTION_SOURCE_REGISTRY_DATABASE_ID", ""
        ),
        notion_article_queue_database_id=os.getenv(
            "NOTION_ARTICLE_QUEUE_DATABASE_ID", ""
        ),
        notion_dataset_meetings_database_id=os.getenv(
            "NOTION_DATASET_MEETINGS_DATABASE_ID", ""
        ),
        notion_newsletters_database_id=os.getenv(
            "NOTION_NEWSLETTERS_DATABASE_ID", ""
        ),
        notion_social_media_database_id=os.getenv(
            "NOTION_SOCIAL_MEDIA_DATABASE_ID", ""
        ),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        aws_region=os.getenv("AWS_REGION", "me-central-1"),
        dynamodb_table_name=os.getenv("DYNAMODB_TABLE_NAME", ""),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME", ""),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
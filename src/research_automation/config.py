"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings for local scripts and deployed handlers."""

    notion_token: str = ""
    notion_articles_database_id: str = ""
    notion_drafts_database_id: str = ""
    llm_provider: str = "openai"
    llm_model: str = ""
    aws_region: str = "us-east-1"
    dynamodb_table_name: str = ""
    s3_bucket_name: str = ""
    log_level: str = "INFO"


def load_settings() -> Settings:
    """Load settings from process environment."""

    return Settings(
        notion_token=os.getenv("NOTION_TOKEN", ""),
        notion_articles_database_id=os.getenv("NOTION_ARTICLES_DATABASE_ID", ""),
        notion_drafts_database_id=os.getenv("NOTION_DRAFTS_DATABASE_ID", ""),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_model=os.getenv("LLM_MODEL", ""),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        dynamodb_table_name=os.getenv("DYNAMODB_TABLE_NAME", ""),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME", ""),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


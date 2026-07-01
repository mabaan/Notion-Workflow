"""Small Notion API client wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from notion_client import Client

NOTION_API_VERSION = "2022-06-28"


@dataclass
class NotionClient:
    """Wrapper around the official Notion client."""

    token: str

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("NOTION_TOKEN is missing.")

        # Keep using the legacy database API shape so the wrapper logic and
        # environment values can stay database_id-based.
        self.client = Client(auth=self.token, notion_version=NOTION_API_VERSION)

    def query_database(
        self,
        database_id: str,
        page_size: int = 10,
        filter_payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query a Notion database and return page results."""

        if not database_id:
            raise ValueError("Database ID is missing.")

        payload: dict[str, Any] = {"page_size": page_size}

        if filter_payload:
            payload["filter"] = filter_payload

        response = self.client.request(
            path=f"databases/{database_id}/query",
            method="POST",
            body=payload,
        )
        return response.get("results", [])

    def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a page in a Notion database."""

        if not database_id:
            raise ValueError("Database ID is missing.")

        return self.client.pages.create(
            parent={"database_id": database_id},
            properties=properties,
            children=children or [],
        )

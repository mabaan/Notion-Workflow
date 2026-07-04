"""Small Notion API client wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from notion_client import Client

NOTION_API_VERSION = "2022-06-28"


@dataclass
class NotionClient:
    """Wrapper around the official Notion client."""

    token: str
    client: Client = field(init=False)

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("NOTION_TOKEN is missing.")

        self.client = Client(auth=self.token, notion_version=NOTION_API_VERSION)

    def query_database(
        self,
        database_id: str,
        page_size: int = 100,
        filter_payload: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query a Notion database and return page results."""

        if not database_id:
            raise ValueError("Database ID is missing.")

        payload: dict[str, Any] = {"page_size": min(page_size, 100)}

        if filter_payload:
            payload["filter"] = filter_payload
        if sorts:
            payload["sorts"] = sorts

        results: list[dict[str, Any]] = []
        next_cursor: str | None = None

        while True:
            if next_cursor:
                payload["start_cursor"] = next_cursor
            elif "start_cursor" in payload:
                del payload["start_cursor"]

            response = self.client.request(
                path=f"databases/{database_id}/query",
                method="POST",
                body=payload,
            )
            batch = response.get("results", [])
            results.extend(batch)

            if max_results is not None and len(results) >= max_results:
                return results[:max_results]

            if not response.get("has_more"):
                return results

            next_cursor = response.get("next_cursor")

    def retrieve_database(self, database_id: str) -> dict[str, Any]:
        """Retrieve a Notion database definition."""

        if not database_id:
            raise ValueError("Database ID is missing.")

        return self.client.request(path=f"databases/{database_id}", method="GET")

    def retrieve_page(self, page_id: str) -> dict[str, Any]:
        """Retrieve a Notion page."""

        if not page_id:
            raise ValueError("Page ID is missing.")

        return self.client.pages.retrieve(page_id=page_id)

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

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Update a page's properties."""

        if not page_id:
            raise ValueError("Page ID is missing.")

        return self.client.pages.update(page_id=page_id, properties=properties)

    def list_block_children(self, block_id: str) -> list[dict[str, Any]]:
        """Return all child blocks for a page or block."""

        if not block_id:
            raise ValueError("Block ID is missing.")

        results: list[dict[str, Any]] = []
        next_cursor: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": 100}
            if next_cursor:
                params["start_cursor"] = next_cursor

            response = self.client.blocks.children.list(block_id=block_id, **params)
            results.extend(response.get("results", []))

            if not response.get("has_more"):
                return results

            next_cursor = response.get("next_cursor")

    def append_block_children(
        self,
        block_id: str,
        children: list[dict[str, Any]],
    ) -> None:
        """Append blocks, chunking requests to satisfy the Notion API."""

        if not block_id:
            raise ValueError("Block ID is missing.")

        for start in range(0, len(children), 100):
            chunk = children[start : start + 100]
            if not chunk:
                continue
            self.client.blocks.children.append(block_id=block_id, children=chunk)

    def delete_block(self, block_id: str) -> dict[str, Any]:
        """Archive a block from a page."""

        if not block_id:
            raise ValueError("Block ID is missing.")

        return self.client.request(path=f"blocks/{block_id}", method="DELETE")

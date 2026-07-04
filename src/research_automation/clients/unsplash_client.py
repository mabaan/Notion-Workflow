"""Unsplash API helpers for newsletter image selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from research_automation.clients.discovery_common import (
    ProviderError,
    ProviderLimitError,
)

UNSPLASH_BASE_URL = "https://api.unsplash.com"


@dataclass
class UnsplashClient:
    """Thin Unsplash API wrapper."""

    access_key: str
    client: httpx.Client = field(init=False)

    def __post_init__(self) -> None:
        if not self.access_key:
            raise ValueError("UNSPLASH_ACCESS_KEY is missing.")

        self.client = httpx.Client(
            base_url=UNSPLASH_BASE_URL,
            headers={
                "Accept-Version": "v1",
                "Authorization": f"Client-ID {self.access_key}",
            },
            follow_redirects=True,
            timeout=30.0,
        )

    def search_photos(
        self,
        *,
        query: str,
        page: int = 1,
        per_page: int = 5,
    ) -> list[dict[str, Any]]:
        """Search Unsplash photos for a query."""

        response = self.client.get(
            "/search/photos",
            params={
                "query": query,
                "page": max(1, page),
                "per_page": max(1, min(per_page, 30)),
                "orientation": "landscape",
                "content_filter": "high",
                "order_by": "relevant",
            },
        )

        if response.status_code in {401, 403, 429}:
            raise ProviderLimitError(
                f"Unsplash quota unavailable: {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Unsplash returned invalid JSON.") from exc

        if response.is_error:
            message = _error_message(payload) or f"Unsplash failed: {response.status_code}"
            raise ProviderError(message)

        results = payload.get("results")
        if not isinstance(results, list):
            return []
        return results


def _error_message(payload: dict[str, Any]) -> str:
    errors = payload.get("errors")
    if isinstance(errors, list):
        messages = [str(item).strip() for item in errors if str(item).strip()]
        if messages:
            return "; ".join(messages)
    return ""

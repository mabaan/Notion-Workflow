"""Brave Search API helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from research_automation.clients.discovery_common import (
    ProviderError,
    ProviderLimitError,
)

BRAVE_BASE_URL = "https://api.search.brave.com/res/v1"


@dataclass
class BraveSearchClient:
    """Thin Brave Search API wrapper."""

    api_key: str
    client: httpx.Client = field(init=False)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY is missing.")

        self.client = httpx.Client(
            base_url=BRAVE_BASE_URL,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
            follow_redirects=True,
            timeout=30.0,
        )

    def search_news(
        self,
        *,
        query: str,
        count: int = 10,
        search_lang: str | None = None,
        freshness: str = "pw",
    ) -> list[dict[str, Any]]:
        """Return Brave news results."""

        params: dict[str, Any] = {
            "q": query,
            "count": max(1, min(count, 50)),
            "freshness": freshness,
        }
        if search_lang:
            params["search_lang"] = search_lang

        data = self._request("/news/search", params)
        results = data.get("results")
        if not isinstance(results, list):
            return []
        return results

    def search_images(
        self,
        *,
        query: str,
        count: int = 10,
        search_lang: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return Brave image results."""

        params: dict[str, Any] = {
            "q": query,
            "count": max(1, min(count, 50)),
        }
        if search_lang:
            params["search_lang"] = search_lang

        data = self._request("/images/search", params)
        results = data.get("results")
        if not isinstance(results, list):
            return []
        return results

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.client.get(path, params=params)

        if response.status_code in {401, 402, 403, 429}:
            raise ProviderLimitError(f"Brave Search quota unavailable: {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Brave Search returned invalid JSON.") from exc

        if response.is_error:
            raise ProviderError(_error_message(payload) or f"Brave Search failed: {response.status_code}")

        return payload


def _error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        detail = error.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
    return ""

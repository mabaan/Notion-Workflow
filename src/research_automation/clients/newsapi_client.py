"""NewsAPI helpers for fallback discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from research_automation.clients.discovery_common import (
    ProviderError,
    ProviderLimitError,
)

NEWSAPI_BASE_URL = "https://newsapi.org/v2"


@dataclass
class NewsApiClient:
    """Thin NewsAPI wrapper."""

    api_key: str
    client: httpx.Client = field(init=False)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("NEWS_API_KEY is missing.")

        self.client = httpx.Client(
            base_url=NEWSAPI_BASE_URL,
            headers={"X-Api-Key": self.api_key},
            follow_redirects=True,
            timeout=30.0,
        )

    def search_everything(
        self,
        *,
        query: str,
        language: str | None = None,
        domains: list[str] | None = None,
        from_iso: str | None = None,
        to_iso: str | None = None,
        page_size: int = 10,
    ) -> list[dict[str, Any]]:
        """Return NewsAPI everything results."""

        params: dict[str, Any] = {
            "q": query,
            "pageSize": max(1, min(page_size, 100)),
            "sortBy": "publishedAt",
        }
        if language:
            params["language"] = language
        if domains:
            params["domains"] = ",".join(domains[:20])
        if from_iso:
            params["from"] = from_iso
        if to_iso:
            params["to"] = to_iso

        response = self.client.get("/everything", params=params)

        if response.status_code in {401, 402, 403, 426, 429}:
            raise ProviderLimitError(f"NewsAPI quota unavailable: {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("NewsAPI returned invalid JSON.") from exc

        if response.is_error or payload.get("status") == "error":
            message = str(payload.get("message") or f"NewsAPI failed: {response.status_code}")
            if response.status_code == 429 or "rate" in message.casefold():
                raise ProviderLimitError(message)
            raise ProviderError(message)

        articles = payload.get("articles")
        if not isinstance(articles, list):
            return []
        return articles

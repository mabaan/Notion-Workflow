"""SerpAPI helpers for image discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from research_automation.clients.discovery_common import (
    ProviderError,
    ProviderLimitError,
)

SERPAPI_BASE_URL = "https://serpapi.com"


@dataclass
class SerpApiClient:
    """Thin SerpAPI wrapper for Google Images."""

    api_key: str
    client: httpx.Client = field(init=False)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is missing.")

        self.client = httpx.Client(
            base_url=SERPAPI_BASE_URL,
            follow_redirects=True,
            timeout=30.0,
        )

    def search_images(
        self,
        *,
        query: str,
        gl: str = "us",
        hl: str = "en",
        num: int = 10,
    ) -> list[dict[str, Any]]:
        """Return SerpAPI Google Images results."""

        response = self.client.get(
            "/search.json",
            params={
                "api_key": self.api_key,
                "engine": "google_images",
                "q": query,
                "gl": gl,
                "hl": hl,
                "num": max(1, min(num, 20)),
            },
        )

        if response.status_code in {401, 402, 403, 429}:
            raise ProviderLimitError(f"SerpAPI quota unavailable: {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("SerpAPI returned invalid JSON.") from exc

        if response.is_error or payload.get("error"):
            message = str(payload.get("error") or f"SerpAPI failed: {response.status_code}")
            if response.status_code == 429 or "rate" in message.casefold():
                raise ProviderLimitError(message)
            raise ProviderError(message)

        results = payload.get("images_results")
        if not isinstance(results, list):
            return []
        return results

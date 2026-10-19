"""Local JSON-backed article deduplication."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class SeenArticleStore:
    """Simple JSON store keyed by article URL hash."""

    path: Path

    def __post_init__(self) -> None:
        self.records = self._load()

    def contains(self, url_hash: str) -> bool:
        """Return whether a URL hash is already known."""

        return url_hash in self.records

    def prune_missing_pages(
        self,
        existing_page_ids: set[str],
        *,
        persist: bool = True,
    ) -> int:
        """Drop records whose Notion page IDs no longer exist."""

        removed = 0
        retained: dict[str, dict[str, str]] = {}

        for url_hash, payload in self.records.items():
            page_id = str(payload.get("notion_page_id") or "")
            if page_id and page_id not in existing_page_ids:
                removed += 1
                continue
            retained[url_hash] = payload

        if removed == 0:
            return 0

        self.records = retained
        if persist:
            self._save()
        return removed

    def record(
        self,
        *,
        url_hash: str,
        title: str,
        canonical_url: str,
        source: str,
        notion_page_id: str,
        created_at: str,
    ) -> None:
        """Save a newly created article page in the store."""

        self.records[url_hash] = {
            "title": title,
            "canonical_url": canonical_url,
            "source": source,
            "notion_page_id": notion_page_id,
            "created_at": created_at,
        }
        self._save()

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}

        contents = self.path.read_text(encoding="utf-8").strip()
        if not contents:
            return {}

        payload = json.loads(contents)
        if not isinstance(payload, dict):
            raise ValueError(f"Seen article store at {self.path} must be a JSON object.")
        return payload

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.records, indent=2, sort_keys=True),
            encoding="utf-8",
        )

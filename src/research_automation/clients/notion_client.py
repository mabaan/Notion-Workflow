"""Notion client boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NotionClient:
    """Small placeholder for Notion operations."""

    token: str

    def is_configured(self) -> bool:
        """Return whether the client has enough configuration to make requests."""

        return bool(self.token)


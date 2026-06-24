"""LLM client boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LlmClient:
    """Small placeholder for LLM operations."""

    provider: str
    model: str

    def is_configured(self) -> bool:
        """Return whether the client has enough configuration to make requests."""

        return bool(self.provider and self.model)


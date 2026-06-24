"""DynamoDB client boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DynamoDbClient:
    """Small placeholder for DynamoDB operations."""

    table_name: str
    region: str

    def is_configured(self) -> bool:
        """Return whether the client has enough configuration to make requests."""

        return bool(self.table_name and self.region)


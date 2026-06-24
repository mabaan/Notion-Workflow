"""S3 client boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class S3Client:
    """Small placeholder for S3 operations."""

    bucket_name: str
    region: str

    def is_configured(self) -> bool:
        """Return whether the client has enough configuration to make requests."""

        return bool(self.bucket_name and self.region)


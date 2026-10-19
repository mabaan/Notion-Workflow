"""Common types for external discovery providers."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Raised when a provider request fails for a non-quota reason."""


class ProviderLimitError(ProviderError):
    """Raised when a provider appears rate-limited or out of credits."""

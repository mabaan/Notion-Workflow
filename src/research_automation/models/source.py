"""Source domain model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Source:
    """Configuration for a source of research articles."""

    name: str
    kind: str
    location: str
    enabled: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


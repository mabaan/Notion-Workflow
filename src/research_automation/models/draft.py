"""Draft domain model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Draft:
    """Generated draft content."""

    title: str
    content: str


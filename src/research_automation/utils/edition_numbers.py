"""Newsletter edition helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Iterable

NEWSLETTER_CODE_RE = re.compile(r"^NL(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class NewsletterEdition:
    """Number, code, and title for a newsletter edition."""

    number: int
    code: str
    title: str


def ordinal(value: int) -> str:
    """Return an ordinal string such as 1st or 22nd."""

    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def parse_newsletter_code(code_value: str) -> int | None:
    """Parse a code like NL097 into an integer."""

    match = NEWSLETTER_CODE_RE.match(code_value.strip())
    if not match:
        return None
    return int(match.group(1))


def next_newsletter_edition(code_values: Iterable[str]) -> NewsletterEdition:
    """Compute the next newsletter code and human title."""

    numbers = [
        number
        for code in code_values
        if (number := parse_newsletter_code(code)) is not None
    ]
    if not numbers:
        raise ValueError("Could not determine the next newsletter code from existing values.")

    next_number = max(numbers) + 1
    return NewsletterEdition(
        number=next_number,
        code=f"NL{next_number:03d}",
        title=f"Newsletter [{ordinal(next_number)} Edition]",
    )

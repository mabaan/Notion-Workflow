"""Helpers for exact regional quota handling."""

from __future__ import annotations

from collections.abc import Iterable

TARGET_REGION_ORDER = ("Global", "UAE", "KSA", "Egypt")

REGION_ALIASES = {
    "global": "Global",
    "uae": "UAE",
    "united arab emirates": "UAE",
    "emirates": "UAE",
    "ksa": "KSA",
    "saudi arabia": "KSA",
    "kingdom of saudi arabia": "KSA",
    "egypt": "Egypt",
    "arab republic of egypt": "Egypt",
}

REGION_KEYWORDS = {
    "UAE": ("uae", "united arab emirates", "dubai", "abu dhabi", "emirati"),
    "KSA": ("ksa", "saudi arabia", "saudi", "riyadh", "jeddah", "neom"),
    "Egypt": ("egypt", "egyptian", "cairo", "alexandria", "suez"),
}

REGION_QUERY_TERMS = {
    "Global": "",
    "UAE": '"UAE" OR "United Arab Emirates" OR Dubai OR Abu Dhabi',
    "KSA": '"KSA" OR "Saudi Arabia" OR Riyadh OR Jeddah OR NEOM',
    "Egypt": "Egypt OR Cairo OR Egyptian",
}


def normalize_exact_region(label: str) -> str | None:
    """Normalize a free-form region label to an exact quota region."""

    return REGION_ALIASES.get(label.strip().casefold())


def primary_target_region(labels: Iterable[str]) -> str | None:
    """Return the first exact quota region represented by a label list."""

    for label in labels:
        region = normalize_exact_region(label)
        if region is not None:
            return region
    return None


def infer_target_region_from_text(text: str) -> str | None:
    """Infer a target region from article text."""

    haystack = text.casefold()
    for region in ("UAE", "KSA", "Egypt"):
        if any(keyword in haystack for keyword in REGION_KEYWORDS[region]):
            return region
    return None


def merge_region_labels(*groups: Iterable[str]) -> list[str]:
    """Merge region labels while preserving order and removing duplicates."""

    merged: list[str] = []
    seen: set[str] = set()

    for group in groups:
        for label in group:
            cleaned = label.strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            merged.append(cleaned)
            seen.add(key)

    return merged


def target_deficits(
    current_counts: dict[str, int],
    target_counts: dict[str, int],
) -> dict[str, int]:
    """Return remaining quota deficits by exact region."""

    return {
        region: max(0, target_counts.get(region, 0) - current_counts.get(region, 0))
        for region in TARGET_REGION_ORDER
    }


def add_primary_region_count(counts: dict[str, int], labels: Iterable[str]) -> None:
    """Increment counts using only the first exact target region found."""

    region = primary_target_region(labels)
    if region is None:
        return
    counts[region] = counts.get(region, 0) + 1


def build_region_query(region: str, topics: Iterable[str]) -> str:
    """Build a provider query for a target region and topic list."""

    topic_clause = " OR ".join(f'"{topic}"' for topic in topics if topic.strip())
    region_clause = REGION_QUERY_TERMS.get(region, "")

    if region_clause and topic_clause:
        return f"({region_clause}) AND ({topic_clause})"
    if region_clause:
        return region_clause
    return topic_clause

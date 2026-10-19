"""Helpers for exact regional quota handling."""

from __future__ import annotations

from collections.abc import Iterable
import re

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
    "UAE": ("uae", "united arab emirates", "dubai", "abu dhabi", "emirati", "sharjah"),
    "KSA": ("ksa", "saudi arabia", "saudi", "riyadh", "jeddah", "neom", "jazan"),
    "Egypt": ("egypt", "egyptian", "cairo", "alexandria", "suez"),
}

# Coverage locations, not new quota regions. Relevant other-MENA events use Global.
OTHER_MENA_LOCATIONS = {
    "Iraq": ("iraq", "iraqi", "baghdad", "basra"),
    "Qatar": ("qatar", "qatari", "doha"),
    "Libya": ("libya", "libyan", "tripoli"),
    "Bahrain": ("bahrain", "bahraini", "manama"),
    "Kuwait": ("kuwait", "kuwaiti"),
    "Oman": ("oman", "omani", "muscat"),
    "Jordan": ("jordan", "jordanian", "amman"),
    "Lebanon": ("lebanon", "lebanese", "beirut"),
    "Iran": ("iran", "iranian", "tehran"),
    "Yemen": ("yemen", "yemeni"),
    "Syria": ("syria", "syrian"),
    "Morocco": ("morocco", "moroccan"),
    "Algeria": ("algeria", "algerian"),
    "Tunisia": ("tunisia", "tunisian"),
    "Sudan": ("sudan", "sudanese"),
    "Israel": ("israel", "israeli"),
    "Palestine": ("palestine", "palestinian", "gaza"),
}


def strip_participant_origins(text: str) -> str:
    """Remove nationality constructions that identify a participant, not a site."""

    return re.sub(
        r"\b(?:saudi|uae|emirati|egyptian|iraqi|qatari|bahraini|kuwaiti|omani)"
        r"(?:['’]s\s+|[- ]based\s+(?=(?:company|firm|developer|contractor|utility)\b)|"
        r"\s+(?=(?:company|firm|developer|contractor|utility)\b))", "", text, flags=re.IGNORECASE,
    )


def reported_location(title: str, snippet: str) -> tuple[str | None, str]:
    """Prefer event location over a counterparty's nationality; leave ties explicit."""

    locations = {**REGION_KEYWORDS, **OTHER_MENA_LOCATIONS}
    aliases = {alias: location for location, names in locations.items() for alias in names}
    names = "|".join(re.escape(name) for name in sorted(aliases, key=len, reverse=True))
    pattern = re.compile(r"(?<!\w)(?:" + names + r")(?!\w)", re.IGNORECASE)

    def locate(text: str) -> tuple[str | None, str]:
        # These describe participants, not where their project takes place.
        text = strip_participant_origins(text)
        matches = list(pattern.finditer(text))
        if not matches:
            return None, ""
        project = re.search(
            r"\b(?:projects?|plants?|facilit\w*|capacity|build\w*|construct\w*|manufactur\w*|"
            r"farms?|flood\w*|drought|renewable|solar|water infrastructure)\b", text, re.IGNORECASE
        )
        if project:
            explicit = re.findall(r"\b(?:in|within|across)\s+(?:the\s+)?(" + names + r")(?!\w)", text, re.IGNORECASE)
            targets = {aliases[name.casefold()] for name in explicit}
            if len(targets) == 1:
                return targets.pop(), "explicit project/event location"
        counts = {location: 0 for location in locations}
        for match in matches:
            counts[aliases[match.group().casefold()]] += 1
        present = [location for location, count in counts.items() if count]
        if len(present) == 1:
            return present[0], "project/event subject" if project else "title geography"
        first = matches[0]
        remainder = text[first.end():]
        if not text[:first.start()].strip() and not re.match(r"\s*(?:and\b|or\b|[&,/])", remainder, re.IGNORECASE):
            return aliases[first.group().casefold()], "project/event subject"
        maximum = max(counts.values())
        leaders = [location for location, count in counts.items() if count == maximum]
        return (leaders[0], "dominant article geography") if len(leaders) == 1 else (None, "ambiguous regional geography")

    location, basis = locate(title)
    if location:
        return location, basis
    description_location, description_basis = locate(snippet)
    if description_location:
        return description_location, "description: " + description_basis
    return None, basis or description_basis

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
    """Use a unique dominant region; fixed iteration order cannot settle a tie."""

    counts = region_mention_counts(text)
    maximum = max(counts.values(), default=0)
    leaders = [region for region, count in counts.items() if count == maximum and count]
    return leaders[0] if len(leaders) == 1 else None


def region_mention_counts(text: str) -> dict[str, int]:
    """Match whole geographic names, counting overlapping aliases only once."""

    return {
        region: len(re.findall(
            r"(?<!\w)(?:" + "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True)) + r")(?!\w)",
            text.casefold(),
        ))
        for region, keywords in REGION_KEYWORDS.items()
    }


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

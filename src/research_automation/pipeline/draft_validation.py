"""Lightweight, advisory checks for generated weekly drafts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Literal

from research_automation.models.draft import DraftArticle
from research_automation.pipeline.images import image_identity
from research_automation.utils.evidence import (
    FEED_CONTENT_LIMITATION,
    has_article_evidence,
    is_feed_content,
)
from research_automation.utils.urls import clean_url, is_google_news_url

DraftKind = Literal["newsletter", "sns"]

_NEWSLETTER_HEADING_RE = re.compile(r"^##\s+", re.MULTILINE)
_SNS_HEADING_RE = re.compile(r"^\s*Topic\s+\d+\s*:", re.IGNORECASE | re.MULTILINE)
_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)
_SOURCES_LABEL_RE = re.compile(r"^\s*Sources?\s*:\s*(?P<value>.*)$", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
_NUMBER_UNIT = (
    r"(?:megawatt-hours?|kilowatt-hours?|gigawatt-hours?|terawatt-hours?|"
    r"megawatts?|kilowatts?|gigawatts?|terawatts?|"
    r"mwh|kwh|gwh|twh|mw|kw|gw|tw|"
    r"percent|percentage|%|million|billion|trillion|"
    r"kilomet(?:er|re)s?|km|m[³3]|cubic\s+met(?:er|re)s?|"
    r"tons?|tonnes?|years?|months?|days?)"
)
_NUMBER_RATE = (
    r"(?:\s*(?:/|per)\s*(?:days?|months?|years?)|"
    r"\s+(?:daily|monthly|annually))?"
)
_NUMBER_RE = re.compile(
    r"(?<![\w])"
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?:\s*(?:(?:more|additional)\s+|-\s*)?"
    r"(?P<unit>" + _NUMBER_UNIT + _NUMBER_RATE + r"))?",
    re.IGNORECASE,
)
_LEADING_RATE_RE = re.compile(
    r"\b(?P<rate>annual|yearly|daily|monthly)"
    r"(?:\s+\w+){0,4}\s+(?:capacity|output)(?:\s+of)?\s*$",
    re.IGNORECASE,
)
_EMPTY_LABEL_RE = re.compile(
    r"^(?:Hook|Define the Issue|Describe the Situation|"
    r"So Why Does This Matter\?|Call-to-Action|SOMA's Perspective):\s*$",
    re.IGNORECASE,
)
_CONTENT_LABEL_RE = re.compile(
    r"^(?:Hook|Define the Issue|Describe the Situation|"
    r"So Why Does This Matter\?|Call-to-Action|SOMA's Perspective):\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NumericClaim:
    display: str
    value: str
    unit: str = ""


def validate_newsletter_draft(
    content: str,
    articles: list[DraftArticle],
) -> list[str]:
    return validate_generated_draft(content, articles, draft_kind="newsletter")


def validate_social_draft(
    content: str,
    articles: list[DraftArticle],
) -> list[str]:
    return validate_generated_draft(content, articles, draft_kind="sns")


def validate_generated_draft(
    content: str,
    articles: list[DraftArticle],
    *,
    draft_kind: DraftKind,
) -> list[str]:
    """Return advisory, story-scoped warnings without changing draft content."""

    label = "Newsletter" if draft_kind == "newsletter" else "SNS"
    sections = _story_sections(content, draft_kind)
    warnings: list[str] = []

    if len(sections) != len(articles):
        warnings.append(
            f"{label}: found {len(sections)} story section(s) for "
            f"{len(articles)} approved article(s)."
        )

    for index, article in enumerate(articles):
        story = _story_label(label, index, article)
        warnings.extend(_evidence_warnings(story, article))
        if index >= len(sections):
            warnings.append(f"{story}: missing story section.")
            continue

        section = sections[index]
        if not _has_story_content(section, draft_kind):
            warnings.append(f"{story}: story section is empty or contains only labels.")
        warnings.extend(_source_warnings(story, section, article))
        warnings.extend(_number_warnings(story, section, article, draft_kind))

    return warnings


def validate_newsletter_images(articles: list[DraftArticle]) -> list[str]:
    """Return warnings for missing, duplicate, or unverifiable story images."""

    warnings: list[str] = []
    seen: dict[str, tuple[int, str]] = {}
    for index, article in enumerate(articles):
        story = _story_label("Newsletter", index, article)
        identity = image_identity(article.image_url)
        if not identity:
            warnings.append(f"{story}: no usable story image was found.")
            continue
        if identity in seen:
            first_index, first_title = seen[identity]
            warnings.append(
                f"{story}: image duplicates Newsletter story {first_index} "
                f"(\"{first_title}\")."
            )
        else:
            seen[identity] = (index + 1, article.title)

        provider = article.image_provider.strip().casefold()
        if provider == "unsplash":
            warnings.append(
                f"{story}: Unsplash stock image is illustrative; verify editorial relevance."
            )
        elif provider == "brave":
            warnings.append(
                f"{story}: Brave image-search result has unverified provenance or relevance."
            )
        elif not provider:
            warnings.append(
                f"{story}: image provider is unknown; verify provenance and relevance."
            )
        else:
            warnings.append(
                f"{story}: image relevance is unverified for provider \"{article.image_provider}\"."
            )
    return warnings


def print_validation_warnings(
    draft_name: str,
    warnings: list[str],
    *,
    output=print,
) -> None:
    if not warnings:
        return
    output(f"{draft_name} quality warnings ({len(warnings)}):")
    for warning in warnings:
        output(f"  - {warning}")


def _story_sections(content: str, draft_kind: DraftKind) -> list[str]:
    pattern = _NEWSLETTER_HEADING_RE if draft_kind == "newsletter" else _SNS_HEADING_RE
    matches = list(pattern.finditer(content or ""))
    return [
        content[match.start() : matches[index + 1].start()].strip()
        if index + 1 < len(matches)
        else content[match.start() :].strip()
        for index, match in enumerate(matches)
    ]


def _evidence_warnings(story: str, article: DraftArticle) -> list[str]:
    status = article.evidence_retrieval_status.strip()
    if not status and not article.factual_points:
        return [f"{story}: Research Notes are missing; checks rely on the summary only."]
    if not has_article_evidence(status):
        return [
            f"{story}: evidence retrieval status is {status or 'unknown'}; "
            "factual checks are limited."
        ]
    if not article.factual_points:
        return [f"{story}: Research Notes contain no factual points."]
    if is_feed_content(status):
        return [f"{story}: {FEED_CONTENT_LIMITATION}"]
    return []


def _source_warnings(
    story: str,
    section: str,
    article: DraftArticle,
) -> list[str]:
    warnings: list[str] = []
    has_sources_label = any(
        _SOURCES_LABEL_RE.match(line) for line in section.splitlines()
    )
    section_urls = _source_urls(section)
    if not has_sources_label:
        warnings.append(f"{story}: missing Sources section.")
    if not section_urls:
        warnings.append(f"{story}: missing source URL.")

    supplied_url = clean_url(article.resolved_publisher_url or article.canonical_url)
    if not supplied_url:
        warnings.append(f"{story}: no publisher source URL is available in article data.")
    elif is_google_news_url(supplied_url):
        warnings.append(f"{story}: publisher URL remains an unresolved Google News link.")
    elif supplied_url not in section_urls:
        warnings.append(f"{story}: supplied publisher URL is missing or altered in the draft.")

    if any(is_google_news_url(url) for url in section_urls):
        warnings.append(f"{story}: draft cites an unresolved Google News URL.")
    return warnings


def _number_warnings(
    story: str,
    section: str,
    article: DraftArticle,
    draft_kind: DraftKind,
) -> list[str]:
    evidence = "\n".join([*article.factual_points, article.summary])
    supported = _numeric_claims(evidence)
    claims = _numeric_claims(_story_claim_text(section, draft_kind))
    warnings: list[str] = []
    reported: set[tuple[str, str]] = set()
    for claim in claims:
        key = (claim.value, claim.unit)
        if key in reported or _claim_is_supported(claim, supported):
            continue
        reported.add(key)
        warnings.append(
            f"{story}: numerical claim \"{claim.display}\" was not matched to "
            "this article's factual points or summary; review it as a possible mismatch."
        )
    return warnings


def _numeric_claims(text: str) -> list[NumericClaim]:
    claims: list[NumericClaim] = []
    without_urls = _URL_RE.sub(" ", text or "")
    without_dates = _DATE_RE.sub(
        lambda match: _append_date_claim(claims, match),
        without_urls,
    )
    for match in _NUMBER_RE.finditer(without_dates):
        normalized = _normalize_number(match.group("number"))
        if not normalized:
            continue
        unit = _normalize_unit(match.group("unit") or "")
        unit = _apply_leading_rate(without_dates, match.start(), unit)
        display = match.group(0).strip()
        claims.append(NumericClaim(display=display, value=normalized, unit=unit))
    return claims


def _append_date_claim(claims: list[NumericClaim], match: re.Match[str]) -> str:
    normalized = "-".join(
        [
            str(int(match.group("year"))),
            str(int(match.group("month"))),
            str(int(match.group("day"))),
        ]
    )
    claims.append(NumericClaim(display=match.group(0), value=normalized, unit="date"))
    return " "


def _normalize_number(value: str) -> str:
    try:
        normalized = Decimal(value.replace(",", "")).normalize()
    except InvalidOperation:
        return ""
    return format(normalized, "f")


def _normalize_unit(unit: str) -> str:
    value = re.sub(r"\s+", " ", unit.casefold().strip()).replace("³", "3")
    value = re.sub(r"\s+per\s+", "/", value)
    value = re.sub(r"\s*/\s*", "/", value)
    rate_words = {"daily": "day", "monthly": "month", "annually": "year"}
    for word, rate in rate_words.items():
        if value.endswith(f" {word}"):
            value = f"{value[: -(len(word) + 1)]}/{rate}"
            break

    base, separator, rate = value.partition("/")
    aliases = {
        "percentage": "%",
        "percent": "%",
        "megawatt": "mw",
        "megawatts": "mw",
        "kilowatt": "kw",
        "kilowatts": "kw",
        "gigawatt": "gw",
        "gigawatts": "gw",
        "terawatt": "tw",
        "terawatts": "tw",
        "megawatt-hour": "mwh",
        "megawatt-hours": "mwh",
        "kilowatt-hour": "kwh",
        "kilowatt-hours": "kwh",
        "gigawatt-hour": "gwh",
        "gigawatt-hours": "gwh",
        "terawatt-hour": "twh",
        "terawatt-hours": "twh",
        "cubic meter": "m3",
        "cubic meters": "m3",
        "cubic metre": "m3",
        "cubic metres": "m3",
        "kilometer": "km",
        "kilometers": "km",
        "kilometre": "km",
        "kilometres": "km",
        "year": "year",
        "years": "year",
        "month": "month",
        "months": "month",
        "day": "day",
        "days": "day",
        "ton": "ton",
        "tons": "ton",
        "tonne": "tonne",
        "tonnes": "tonne",
    }
    normalized_base = aliases.get(base, base)
    if not separator:
        return normalized_base
    normalized_rate = aliases.get(rate, rate)
    return f"{normalized_base}/{normalized_rate}"


def _apply_leading_rate(text: str, number_start: int, unit: str) -> str:
    if not unit or "/" in unit or unit in {"%", "million", "billion", "trillion"}:
        return unit
    match = _LEADING_RATE_RE.search(text[max(0, number_start - 80) : number_start])
    if not match:
        return unit
    rates = {
        "annual": "year",
        "yearly": "year",
        "daily": "day",
        "monthly": "month",
    }
    return f"{unit}/{rates[match.group('rate').casefold()]}"


def _claim_is_supported(claim: NumericClaim, supported: list[NumericClaim]) -> bool:
    same_value = [item for item in supported if item.value == claim.value]
    if not same_value:
        return False
    if not claim.unit:
        return True
    return any(
        item.unit == claim.unit
        or ("/" not in claim.unit and item.unit.startswith(f"{claim.unit}/"))
        for item in same_value
    )


def _story_claim_text(section: str, draft_kind: DraftKind) -> str:
    lines: list[str] = []
    in_sources = False
    for index, raw_line in enumerate(section.splitlines()):
        line = raw_line.strip()
        if _SOURCES_LABEL_RE.match(line):
            in_sources = True
            continue
        if in_sources or line.startswith("![") or (line.startswith("#") and not line.startswith("##")):
            continue
        if draft_kind == "sns" and index == 0:
            line = re.sub(r"^Topic\s+\d+\s*:\s*", "", line, flags=re.IGNORECASE)
        elif draft_kind == "newsletter" and index == 0:
            line = re.sub(r"^##\s+", "", line)
        line = _CONTENT_LABEL_RE.sub("", line)
        lines.append(_URL_RE.sub(" ", line))
    return "\n".join(lines)


def _has_story_content(section: str, draft_kind: DraftKind) -> bool:
    lines = section.splitlines()[1:]
    in_sources = False
    for raw_line in lines:
        line = raw_line.strip()
        if _SOURCES_LABEL_RE.match(line):
            in_sources = True
            continue
        if in_sources or not line or line.startswith("!["):
            continue
        if line.startswith("#") and not line.startswith("##"):
            continue
        if _EMPTY_LABEL_RE.match(line) or _URL_RE.fullmatch(line):
            continue
        return True
    return False


def _clean_extracted_url(value: str) -> str:
    return clean_url(value.rstrip(".,;:!?\"'"))


def _source_urls(section: str) -> list[str]:
    urls: list[str] = []
    in_sources = False
    for line in section.splitlines():
        match = _SOURCES_LABEL_RE.match(line)
        if match:
            in_sources = True
            line = match.group("value")
        if not in_sources:
            continue
        urls.extend(
            cleaned
            for value in _URL_RE.findall(line)
            if (cleaned := _clean_extracted_url(value))
        )
    return urls


def _story_label(label: str, index: int, article: DraftArticle) -> str:
    return f'{label} story {index + 1} ("{article.title}")'

"""Editorial relevance helpers for article ingestion."""

from __future__ import annotations

from collections.abc import Iterable
import re

from research_automation.models.article import Article, EnrichedArticle
from research_automation.utils.text import normalize_whitespace

_TOKEN_RE = re.compile(r"[a-z0-9]+")

TOPIC_KEYWORDS = {
    "food security": (
        "food security",
        "food system",
        "agri-food",
        "agrifood",
        "agriculture",
        "agricultur",
        "farming",
        "farm",
        "crop",
        "grain",
        "fertilizer",
        "livestock",
        "aquaculture",
    ),
    "water security": (
        "water security",
        "water treatment",
        "water reuse",
        "water utility",
        "drinking water",
        "groundwater",
        "wastewater",
        "waste water",
        "desalination",
        "desal",
        "irrigation",
        "aquifer",
        "water",
    ),
    "net zero transition": (
        "net zero",
        "decarbon",
        "emission",
        "carbon",
        "climate target",
        "climate policy",
        "energy efficiency",
        "electrification",
    ),
    "energy transition": (
        "energy transition",
        "renewable",
        "solar",
        "wind",
        "battery",
        "storage",
        "grid",
        "electricity",
        "power sector",
        "hydrogen",
        "lng",
        "oil",
        "gas",
        "petrochem",
    ),
    "trade": (
        "trade",
        "trading",
        "export",
        "import",
        "tariff",
        "shipping",
        "logistics",
        "port",
        "commodity",
        "corridor",
    ),
    "resilience": (
        "resilience",
        "adaptation",
        "drought",
        "heatwave",
        "flood",
        "flooding",
        "water stress",
        "disruption",
    ),
    "regulation": (
        "regulation",
        "regulatory",
        "policy",
        "legislation",
        "law",
        "compliance",
        "standard",
        "framework",
    ),
    "supply chains": (
        "supply chain",
        "supply chains",
        "shipping",
        "logistics",
        "freight",
        "port",
        "corridor",
    ),
    "desalination": (
        "desalination",
        "desal",
        "reverse osmosis",
        "brine",
    ),
    "agri-food": (
        "agri-food",
        "agrifood",
        "food system",
        "agriculture",
        "agricultur",
        "crop",
        "grain",
        "fertilizer",
        "farm",
        "farming",
        "livestock",
    ),
}

INTEREST_GEO_KEYWORDS = (
    "mena",
    "middle east",
    "gulf",
    "gcc",
    "uae",
    "united arab emirates",
    "dubai",
    "abu dhabi",
    "ksa",
    "saudi",
    "saudi arabia",
    "riyadh",
    "jeddah",
    "neom",
    "egypt",
    "egyptian",
    "cairo",
    "suez",
    "bahrain",
    "kuwait",
    "oman",
    "qatar",
)

OUTSIDE_INTEREST_LOCATION_KEYWORDS = (
    "alaska",
    "america",
    "american",
    "australia",
    "beijing",
    "britain",
    "canada",
    "central asia",
    "chennai",
    "china",
    "chinese",
    "cote d'ivoire",
    "delhi",
    "england",
    "europe",
    "european",
    "florida",
    "india",
    "indian",
    "indonesia",
    "ireland",
    "japan",
    "latin america",
    "melbourne",
    "mexico",
    "modi",
    "nepal",
    "pakistan",
    "thailand",
    "tribal",
    "trump",
    "uk ",
    "u.s.",
    "us epa",
    "usa",
    "united states",
    "venezuela",
    "washington",
)


def matched_company_topics(
    article: Article,
    company_topics: Iterable[str],
) -> list[str]:
    """Return company focus areas clearly signaled by the article text."""

    text = _normalized_text(article)
    if not text:
        return []

    tokens = tuple(_TOKEN_RE.findall(text))
    matched: list[str] = []
    seen: set[str] = set()

    for topic in company_topics:
        label = normalize_whitespace(topic)
        topic_key = label.casefold()
        if not label or topic_key in seen:
            continue
        seen.add(topic_key)

        keywords = TOPIC_KEYWORDS.get(topic_key, (topic_key,))
        if any(_matches_keyword(text, tokens, keyword) for keyword in keywords):
            matched.append(label)

    return matched


def article_has_company_focus(
    article: Article,
    company_topics: Iterable[str],
) -> bool:
    """Return whether an article is clearly within the company's coverage scope."""

    return bool(matched_company_topics(article, company_topics))


def article_has_interest_geography(article: Article) -> bool:
    """Return whether the article is not just a local story outside the coverage region."""

    text = _normalized_text(article)
    if not text:
        return False

    if any(keyword in text for keyword in INTEREST_GEO_KEYWORDS):
        return True

    return not any(keyword in text for keyword in OUTSIDE_INTEREST_LOCATION_KEYWORDS)


def meets_minimum_relevance(
    enriched: EnrichedArticle,
    minimum_score: int,
) -> bool:
    """Return whether an LLM-enriched article clears the configured threshold."""

    return enriched.relevance_score >= max(1, minimum_score)


def _normalized_text(article: Article) -> str:
    return normalize_whitespace(f"{article.title} {article.snippet}").casefold()


def _matches_keyword(text: str, tokens: tuple[str, ...], keyword: str) -> bool:
    normalized_keyword = normalize_whitespace(keyword).casefold()
    if not normalized_keyword:
        return False

    if " " in normalized_keyword or "-" in normalized_keyword:
        return normalized_keyword in text

    if normalized_keyword in tokens:
        return True

    if len(normalized_keyword) >= 5:
        return any(token.startswith(normalized_keyword) for token in tokens)

    return False

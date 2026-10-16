"""Editorial relevance helpers for article ingestion."""

from __future__ import annotations

from collections.abc import Iterable
import re

from research_automation.models.article import Article, EnrichedArticle
from research_automation.utils.regions import OTHER_MENA_LOCATIONS, strip_participant_origins
from research_automation.utils.text import normalize_whitespace

_TOKEN_RE = re.compile(r"[a-z0-9]+")

DIRECT_TOPIC_KEYWORDS = {
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
        "veal",
        "harvest",
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
        "nile dam",
        "nile basin",
        "dam dispute",
        "river basin",
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
        "renewable",
        "solar",
        "wind",
        "battery",
        "energy storage",
        "battery storage",
        "grid",
        "hydrogen",
        "clean energy",
        "low-carbon",
    ),
    "energy transition": (
        "energy transition",
        "renewable",
        "solar",
        "wind",
        "battery",
        "energy storage",
        "battery storage",
        "grid",
        "hydrogen",
        "clean energy",
        "low-carbon",
    ),
    "resilience": (
        "drought",
        "flood",
        "flooding",
        "water stress",
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
        "veal",
        "harvest",
    ),
}

# These signals can make a story relevant, but they need an explicit bridge to a
# mission theme before they should outrank food, water, or transition coverage.
CONTEXTUAL_TOPIC_KEYWORDS = {
    "net zero transition": (
        "climate",
        "electricity",
        "power sector",
    ),
    "energy transition": (
        "electricity",
        "power sector",
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
        "heatwave",
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
    "bahraini",
    "kuwait",
    "oman",
    "qatar",
    *(alias for aliases in OTHER_MENA_LOCATIONS.values() for alias in aliases),
)

OUTSIDE_INTEREST_LOCATION_KEYWORDS = (
    "istanbul",
    "turkey",
    "turkish",
    "paris",
    "france",
    "berlin",
    "germany",
    "sydney",
    "boston",
    "mumbai",
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

# Explicit variants only: broad stemming would confuse e.g. gas/gases and news.
_MISSION_VARIANTS = {
    "grid": ("grids",),
    "crop": ("crops",),
    "farm": ("farms",),
    "battery": ("batteries",),
    "water utility": ("water utilities",),
    "food system": ("food systems",),
    "fertilizer": ("fertiliser", "fertilisers"),
    "energy efficiency": ("energy efficiencies",),
    "policy": ("policies",),
}


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase.strip()) + r"(?!\w)", text))


def has_global_systemic_scope(article: Article) -> bool:
    """Recognize explicit mission systems, never the word 'global' alone."""

    text = _normalized_text(article)
    if re.search(
        r"\b(?:global|world(?:wide)?) (?:food|fertili[sz]er|grain|water|energy|solar|battery|carbon) "
        r"(?:supply|security|markets?|prices?|shortages?|trade)\b", text
    ):
        return True
    if (
        re.search(r"\b(?:hormuz|suez canal)\b", text)
        and re.search(r"\b(?:fertili[sz]er|food security|food crisis|grain supplies|harvests?)\b", text)
        and re.search(r"\b(?:supply|supplies|shipping|disruption|crisis|trade)\b", text)
    ):
        return True
    if (
        re.search(r"\b(?:world bank|islamic development bank|fao|united nations)\b", text)
        and re.search(r"\b(?:food security|water security|renewable energy|decarbon\w*)\b", text)
        and re.search(r"\b(?:mobilis\w*|mobiliz\w*|funding|financing|invest\w*|supply)\b", text)
    ):
        return True
    # A MENA actor investing across overseas grid markets is not foreign local news.
    return bool(
        any(_contains_phrase(text, word) for word in INTEREST_GEO_KEYWORDS)
        and re.search(r"\bacross (?:the )?(?:us|u\.s\.|europe)\b", text)
        and re.search(r"\b(?:invest\w*|agreements?)\b", text)
        and re.search(r"\b(?:power grids?|renewable energy|battery storage)\b", text)
    )


def is_foreign_local_article(article: Article) -> bool:
    """Detect explicit outside-scope local coverage without consulting publisher location."""

    title = strip_participant_origins(normalize_whitespace(article.title)).casefold()
    local_focus = re.search(r"\b(?:schools?|municipal|city council|local residents|urban water|local infrastructure)\b", title)
    return bool(
        any(_contains_phrase(title, word) for word in OUTSIDE_INTEREST_LOCATION_KEYWORDS)
        and not any(_contains_phrase(strip_participant_origins(_normalized_text(article)), word) for word in INTEREST_GEO_KEYWORDS)
        and (local_focus or not has_global_systemic_scope(article))
    )


def metadata_mission_strength(article: Article, topics: Iterable[str]) -> tuple[int, bool]:
    """Small bounded metadata hints, not a substitute for editorial scoring."""

    direct = set(matched_direct_mission_signals(article, topics))
    core = direct - {"resilience"}
    text = _normalized_text(article)
    specific = re.search(
        r"\b(?:food security|fertili[sz]ers?|desalination|wastewater|water reuse|"
        r"water treatment|irrigation|battery|batteries|power grids?|decarbon\w*)\b", text
    )
    # Don't count synonymous topic labels twice, or reward free-standing numbers.
    strength = (2 + int(bool(specific))) if core else int(bool(direct))
    concrete = bool(core and re.search(
        r"\b(?:projects?|plants?|facilit\w*|invest\w*|technolog\w*|capacity|"
        r"agreements?|contracts?|approv\w*|commissioned|commissioning|commissions|legislation|mandates?|"
        r"policy changes?|regulations?)\b", text
    ))
    return strength, concrete


def matched_company_topics(
    article: Article,
    company_topics: Iterable[str],
) -> list[str]:
    """Return direct or contextual company focus areas signaled by the article."""

    return _matched_topics(
        article,
        company_topics,
        DIRECT_TOPIC_KEYWORDS,
        CONTEXTUAL_TOPIC_KEYWORDS,
        use_topic_as_fallback=True,
    )


def matched_direct_mission_signals(
    article: Article,
    company_topics: Iterable[str],
) -> list[str]:
    """Return configured topics supported by a direct mission signal."""

    matches = _matched_topics(article, company_topics, DIRECT_TOPIC_KEYWORDS)
    if _battery_without_application(article):
        matches = [topic for topic in matches if topic.casefold() not in {"energy transition", "net zero transition"}]
    return matches


def _battery_without_application(article: Article) -> bool:
    """A battery noun or materials paper alone does not demonstrate transition relevance."""

    text = _normalized_text(article)
    if not re.search(r"\bbatter(?:y|ies)\b", text):
        return False
    application = re.search(
        r"\b(?:energy transition|net[- ]zero|decarbon\w*|energy storage|grid|grids|"
        r"renewable\w*|solar|wind|electric vehicles?|evs?|charging|recycl\w*|"
        r"commercial\w*|manufactur\w*|factor\w*|assembly|deploy\w*|pilot|utility[- ]scale|"
        r"battery suppl\w*|batter(?:y|ies) (?:projects?|plants?|facilit\w*)|"
        r"mwh|gwh|megawatt\w*|gigawatt\w*)\b", text
    )
    other_mission = _matched_topics(
        article, ("food security", "water security", "desalination", "agri-food"), DIRECT_TOPIC_KEYWORDS
    )
    return not application and not other_mission


def metadata_rejection_reason(article: Article, direct_signals: Iterable[str]) -> str:
    """Reject demonstrated off-mission classes, keeping contextual mission bridges."""

    if _battery_without_application(article):
        return "battery coverage without a transition application"
    core = set(direct_signals) - {"resilience"}
    text = _normalized_text(article)
    if not core and (
        re.search(r"\b(?:crypto\w*|bitcoin|digital assets?)\b", text)
        or re.search(r"\b(?:flights?|passengers?|travellers?|travelers?)\b", text)
    ):
        return "consumer finance or passenger travel without a direct mission consequence"
    return ""


def matched_contextual_signals(
    article: Article,
    company_topics: Iterable[str],
) -> list[str]:
    """Return configured topics supported by broad contextual language."""

    return _matched_topics(article, company_topics, CONTEXTUAL_TOPIC_KEYWORDS)


def _matched_topics(
    article: Article,
    company_topics: Iterable[str],
    *keyword_groups: dict[str, tuple[str, ...]],
    use_topic_as_fallback: bool = False,
) -> list[str]:
    """Match configured topics against one or more keyword groups."""

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

        keywords = tuple(
            keyword
            for group in keyword_groups
            for keyword in group.get(topic_key, ())
        )
        if not keywords and use_topic_as_fallback:
            keywords = (topic_key,)
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

    if is_foreign_local_article(article):
        return False
    if has_global_systemic_scope(article):
        return True
    if any(_contains_phrase(text, keyword) for keyword in INTEREST_GEO_KEYWORDS):
        return True

    return not any(_contains_phrase(text, keyword) for keyword in OUTSIDE_INTEREST_LOCATION_KEYWORDS)


def meets_minimum_relevance(
    enriched: EnrichedArticle,
    minimum_score: int,
) -> bool:
    """Return whether an LLM-enriched article clears the configured threshold."""

    return enriched.relevance_score >= max(1, minimum_score)


def _normalized_text(article: Article) -> str:
    text = normalize_whitespace(f"{article.title} {article.snippet}").casefold()
    # Remove explicitly negated mentions; 'not only water' and 'not enough water'
    # still describe water, and substantive unnegated mentions remain available.
    return re.sub(
        r"\b(?:not|neither|nor)\s+(?:about\s+)?(?:water|energy|carbon|solar|wind|food security)\b",
        "", text,
    )


def _matches_keyword(text: str, tokens: tuple[str, ...], keyword: str) -> bool:
    normalized_keyword = normalize_whitespace(keyword).casefold()
    if not normalized_keyword:
        return False

    if any(_contains_phrase(text, variant) for variant in _MISSION_VARIANTS.get(normalized_keyword, ())):
        return True

    if " " in normalized_keyword or "-" in normalized_keyword:
        return normalized_keyword in text

    if normalized_keyword in tokens:
        return True

    if normalized_keyword in {"water", "carbon"}:
        # Waterfront real estate and carbonara are not mission evidence.
        return False

    if len(normalized_keyword) >= 5:
        return any(token.startswith(normalized_keyword) for token in tokens)

    return False

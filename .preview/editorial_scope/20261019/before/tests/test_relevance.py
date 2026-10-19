import pytest

from research_automation.models.article import Article, EnrichedArticle
from research_automation.pipeline.relevance import (
    article_has_interest_geography,
    article_has_company_focus,
    matched_company_topics,
    matched_contextual_signals,
    matched_direct_mission_signals,
    meets_minimum_relevance,
)


COMPANY_TOPICS = (
    "food security",
    "water security",
    "net zero transition",
    "energy transition",
    "trade",
    "resilience",
    "regulation",
    "supply chains",
    "desalination",
    "agri-food",
)


def test_article_has_company_focus_for_water_infrastructure() -> None:
    article = Article(
        title="Saudi Arabia opens major wastewater treatment plant",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet="The project expands desalination and water reuse capacity.",
    )

    assert article_has_company_focus(
        article,
        ("food security", "water security", "net zero transition"),
    )
    assert matched_company_topics(
        article,
        ("food security", "water security", "net zero transition"),
    ) == ["water security"]


def test_article_has_company_focus_rejects_consumer_ai_story() -> None:
    article = Article(
        title="UAE emerges as one of the world's most receptive markets for AI-powered shopping",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet="Retail brands are experimenting with smoother checkout experiences.",
    )

    assert not article_has_company_focus(
        article,
        ("food security", "water security", "net zero transition", "trade"),
    )


def test_article_has_company_focus_rejects_bank_mandate_story() -> None:
    article = Article(
        title="Abu Dhabi bank mandates three-year Euro green benchmark",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet="Initial price thoughts were released for the debt transaction.",
    )

    assert not article_has_company_focus(
        article,
        ("food security", "water security", "net zero transition", "regulation"),
    )


def test_meets_minimum_relevance_uses_threshold() -> None:
    enriched = EnrichedArticle(
        summary="Summary",
        why_it_matters="Why it matters",
        relevance_score=3,
    )

    assert not meets_minimum_relevance(enriched, 4)
    assert meets_minimum_relevance(enriched, 3)


def test_article_has_interest_geography_rejects_local_outside_region_story() -> None:
    article = Article(
        title="ADB backs $230 million investment to upgrade Chennai urban water systems",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet="The project improves sanitation infrastructure in India.",
    )

    assert not article_has_interest_geography(article)


def test_article_has_interest_geography_accepts_gulf_water_story() -> None:
    article = Article(
        title="Samsung E&A secures Middle East water contract",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet="The project expands water infrastructure across the Gulf.",
    )

    assert article_has_interest_geography(article)


def test_article_has_interest_geography_rejects_us_energy_story() -> None:
    article = Article(
        title="Union workers decry Trump's war on wind",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet="The US energy debate is reshaping local renewable jobs.",
    )

    assert not article_has_interest_geography(article)


@pytest.mark.parametrize(
    ("title", "snippet"),
    [
        (
            "Sharjah invests in its next water infrastructure cycle",
            "The plan adds water production and waste treatment capacity.",
        ),
        (
            "Failure to activate Hormuz fertilizer plan could trigger food crisis",
            "The disruption could constrain fertilizer supplies and food security.",
        ),
        (
            "Egypt to get new lithium-ion battery assembly facility",
            "The facility will assemble batteries for regional markets.",
        ),
        (
            "Iraq in talks with ACWA to increase solar capacity",
            "The project would add utility-scale renewable generation.",
        ),
    ],
)
def test_direct_mission_stories_have_deterministic_direct_signals(
    title: str,
    snippet: str,
) -> None:
    article = Article(
        title=title,
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet=snippet,
    )

    assert matched_direct_mission_signals(article, COMPANY_TOPICS)
    assert article_has_company_focus(article, COMPANY_TOPICS)


@pytest.mark.parametrize(
    ("title", "snippet"),
    [
        (
            "Strait attacks intensify against oil shipping",
            "Several conventional oil vessels were struck during the conflict.",
        ),
        (
            "OPEC oil output rises in September",
            "Members increased conventional crude production.",
        ),
        (
            "Oil depot strikes escalate regional conflict",
            "The attacks damaged petroleum storage sites.",
        ),
        (
            "Minister opens unrelated dry port",
            "The logistics terminal expands freight and trade capacity.",
        ),
    ],
)
def test_broad_context_stays_eligible_without_becoming_a_direct_signal(
    title: str,
    snippet: str,
) -> None:
    article = Article(
        title=title,
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        snippet=snippet,
    )

    assert matched_direct_mission_signals(article, COMPANY_TOPICS) == []
    assert matched_contextual_signals(article, COMPANY_TOPICS)
    assert article_has_company_focus(article, COMPANY_TOPICS)

from research_automation.models.article import Article, EnrichedArticle
from research_automation.pipeline.relevance import (
    article_has_interest_geography,
    article_has_company_focus,
    matched_company_topics,
    meets_minimum_relevance,
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

from research_automation.models.article import Article
from research_automation.pipeline.discovery import (
    assign_article_target_region,
    choose_next_article_for_admission,
    prioritize_articles_for_admission,
    select_feed_articles_for_run,
)
from research_automation.utils.regions import primary_target_region


def test_assign_article_target_region_prefers_specific_text_over_broad_source() -> None:
    article = Article(
        title="Egypt pushes new desalination investment",
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        source_name="Example",
        source_page_id="source-1",
        region=["Global", "MENA"],
        snippet="Cairo is accelerating water infrastructure plans.",
    )

    assign_article_target_region(article)

    assert primary_target_region(article.region) == "Egypt"
    assert article.region[0] == "Egypt"


def test_select_feed_articles_prioritizes_unfilled_target_buckets() -> None:
    articles = [
        Article(
            title="Global trade update",
            url="https://example.com/global",
            canonical_url="https://example.com/global",
            source_name="Global Source",
            source_page_id="source-global",
            region=["Global"],
        ),
        Article(
            title="UAE grid investment rises",
            url="https://example.com/uae",
            canonical_url="https://example.com/uae",
            source_name="UAE Source",
            source_page_id="source-uae",
            region=["UAE", "GCC"],
        ),
        Article(
            title="KSA desalination pipeline expands",
            url="https://example.com/ksa",
            canonical_url="https://example.com/ksa",
            source_name="KSA Source",
            source_page_id="source-ksa",
            region=["KSA", "GCC"],
        ),
        Article(
            title="Generic MENA market roundup",
            url="https://example.com/mena",
            canonical_url="https://example.com/mena",
            source_name="MENA Source",
            source_page_id="source-mena",
            region=["MENA"],
        ),
    ]

    selected, deficits = select_feed_articles_for_run(
        articles,
        current_counts={"Global": 0, "UAE": 0, "KSA": 0, "Egypt": 0},
        target_counts={"Global": 1, "UAE": 1, "KSA": 1, "Egypt": 1},
        limit=3,
    )

    assert [primary_target_region(article.region) for article in selected] == [
        "Global",
        "UAE",
        "KSA",
    ]
    assert deficits["Egypt"] == 1


def test_select_feed_articles_backfills_with_source_diversity() -> None:
    articles = [
        Article(
            title="A1",
            url="https://example.com/a1",
            canonical_url="https://example.com/a1",
            source_name="Source A",
            source_page_id="source-a",
            region=["MENA"],
        ),
        Article(
            title="A2",
            url="https://example.com/a2",
            canonical_url="https://example.com/a2",
            source_name="Source A",
            source_page_id="source-a",
            region=["MENA"],
        ),
        Article(
            title="B1",
            url="https://example.com/b1",
            canonical_url="https://example.com/b1",
            source_name="Source B",
            source_page_id="source-b",
            region=["MENA"],
        ),
        Article(
            title="C1",
            url="https://example.com/c1",
            canonical_url="https://example.com/c1",
            source_name="Source C",
            source_page_id="source-c",
            region=["MENA"],
        ),
    ]

    selected, _ = select_feed_articles_for_run(
        articles,
        current_counts={"Global": 2, "UAE": 2, "KSA": 2, "Egypt": 2},
        target_counts={"Global": 2, "UAE": 2, "KSA": 2, "Egypt": 2},
        limit=3,
    )

    assert [article.source_name for article in selected] == [
        "Source A",
        "Source B",
        "Source C",
    ]


def test_select_feed_articles_balances_quota_slots_across_sources() -> None:
    articles = [
        Article(
            title="A1",
            url="https://example.com/a1",
            canonical_url="https://example.com/a1",
            source_name="Source A",
            source_page_id="source-a",
            region=["Global"],
        ),
        Article(
            title="A2",
            url="https://example.com/a2",
            canonical_url="https://example.com/a2",
            source_name="Source A",
            source_page_id="source-a",
            region=["Global"],
        ),
        Article(
            title="B1",
            url="https://example.com/b1",
            canonical_url="https://example.com/b1",
            source_name="Source B",
            source_page_id="source-b",
            region=["Global"],
        ),
    ]

    selected, deficits = select_feed_articles_for_run(
        articles,
        current_counts={"Global": 0, "UAE": 0, "KSA": 0, "Egypt": 0},
        target_counts={"Global": 2, "UAE": 0, "KSA": 0, "Egypt": 0},
        limit=2,
    )

    assert [article.source_name for article in selected] == [
        "Source A",
        "Source B",
    ]
    assert deficits["Global"] == 0


def test_prioritize_articles_for_admission_frontloads_deficit_regions() -> None:
    articles = [
        Article(
            title="Global 1",
            url="https://example.com/g1",
            canonical_url="https://example.com/g1",
            source_name="Global Source",
            source_page_id="source-global",
            region=["Global"],
        ),
        Article(
            title="Global 2",
            url="https://example.com/g2",
            canonical_url="https://example.com/g2",
            source_name="Global Source",
            source_page_id="source-global",
            region=["Global"],
        ),
        Article(
            title="UAE 1",
            url="https://example.com/u1",
            canonical_url="https://example.com/u1",
            source_name="UAE Source",
            source_page_id="source-uae",
            region=["UAE", "GCC"],
        ),
        Article(
            title="KSA 1",
            url="https://example.com/k1",
            canonical_url="https://example.com/k1",
            source_name="KSA Source",
            source_page_id="source-ksa",
            region=["KSA", "GCC"],
        ),
        Article(
            title="Egypt 1",
            url="https://example.com/e1",
            canonical_url="https://example.com/e1",
            source_name="Egypt Source",
            source_page_id="source-egypt",
            region=["Egypt", "MENA"],
        ),
    ]

    ordered = prioritize_articles_for_admission(
        articles,
        current_counts={"Global": 0, "UAE": 0, "KSA": 0, "Egypt": 0},
        target_counts={"Global": 2, "UAE": 2, "KSA": 2, "Egypt": 2},
    )

    assert [primary_target_region(article.region) for article in ordered[:4]] == [
        "Global",
        "UAE",
        "KSA",
        "Egypt",
    ]


def test_prioritize_articles_for_admission_skips_regions_without_deficits_first() -> None:
    articles = [
        Article(
            title="Global 1",
            url="https://example.com/g1",
            canonical_url="https://example.com/g1",
            source_name="Global Source",
            source_page_id="source-global",
            region=["Global"],
        ),
        Article(
            title="UAE 1",
            url="https://example.com/u1",
            canonical_url="https://example.com/u1",
            source_name="UAE Source",
            source_page_id="source-uae",
            region=["UAE", "GCC"],
        ),
        Article(
            title="KSA 1",
            url="https://example.com/k1",
            canonical_url="https://example.com/k1",
            source_name="KSA Source",
            source_page_id="source-ksa",
            region=["KSA", "GCC"],
        ),
    ]

    ordered = prioritize_articles_for_admission(
        articles,
        current_counts={"Global": 2, "UAE": 0, "KSA": 0, "Egypt": 0},
        target_counts={"Global": 2, "UAE": 2, "KSA": 2, "Egypt": 2},
    )

    assert [primary_target_region(article.region) for article in ordered[:2]] == [
        "UAE",
        "KSA",
    ]


def test_choose_next_article_for_admission_tracks_live_deficits() -> None:
    articles = [
        Article(
            title="Egypt 1",
            url="https://example.com/e1",
            canonical_url="https://example.com/e1",
            source_name="Egypt Source",
            source_page_id="source-egypt",
            region=["Egypt", "MENA"],
        ),
        Article(
            title="UAE 1",
            url="https://example.com/u1",
            canonical_url="https://example.com/u1",
            source_name="UAE Source",
            source_page_id="source-uae",
            region=["UAE", "GCC"],
        ),
        Article(
            title="Global 1",
            url="https://example.com/g1",
            canonical_url="https://example.com/g1",
            source_name="Global Source",
            source_page_id="source-global",
            region=["Global"],
        ),
    ]

    candidate = choose_next_article_for_admission(
        articles,
        current_counts={"Global": 2, "UAE": 0, "KSA": 2, "Egypt": 1},
        target_counts={"Global": 2, "UAE": 2, "KSA": 2, "Egypt": 2},
        source_counts={},
        max_per_source=2,
        deficits_only=True,
        allow_source_cap_override=False,
    )

    assert candidate is not None
    assert primary_target_region(candidate.region) == "UAE"


def test_choose_next_article_for_admission_softens_source_cap_for_missing_region() -> None:
    articles = [
        Article(
            title="UAE 1",
            url="https://example.com/u1",
            canonical_url="https://example.com/u1",
            source_name="UAE Source",
            source_page_id="source-uae",
            region=["UAE", "GCC"],
        ),
        Article(
            title="Global 1",
            url="https://example.com/g1",
            canonical_url="https://example.com/g1",
            source_name="Global Source",
            source_page_id="source-global",
            region=["Global"],
        ),
    ]

    hard_cap_candidate = choose_next_article_for_admission(
        articles,
        current_counts={"Global": 2, "UAE": 1, "KSA": 2, "Egypt": 2},
        target_counts={"Global": 2, "UAE": 2, "KSA": 2, "Egypt": 2},
        source_counts={"UAE Source": 2},
        max_per_source=2,
        deficits_only=True,
        allow_source_cap_override=False,
    )
    soft_cap_candidate = choose_next_article_for_admission(
        articles,
        current_counts={"Global": 2, "UAE": 1, "KSA": 2, "Egypt": 2},
        target_counts={"Global": 2, "UAE": 2, "KSA": 2, "Egypt": 2},
        source_counts={"UAE Source": 2},
        max_per_source=2,
        deficits_only=True,
        allow_source_cap_override=True,
    )

    assert hard_cap_candidate is None
    assert soft_cap_candidate is not None
    assert primary_target_region(soft_cap_candidate.region) == "UAE"

from research_automation.models.draft import DraftArticle
from research_automation.pipeline.draft_validation import (
    validate_newsletter_draft,
    validate_newsletter_images,
    validate_social_draft,
)


def _article(
    title: str,
    url: str,
    *,
    facts: list[str] | None = None,
    summary: str = "",
    status: str = "Extracted",
) -> DraftArticle:
    return DraftArticle(
        title=title,
        source_name="Test Publisher",
        canonical_url=url,
        summary=summary,
        factual_points=list(facts or []),
        evidence_retrieval_status=status,
    )


def _newsletter_story(title: str, body: str, url: str) -> str:
    return "\n".join(
        [
            f"## {title}",
            "#NetZeroTransition",
            body,
            "A second evidence-based paragraph.",
            "A third evidence-based paragraph.",
            "SOMA's Perspective:",
            "The project status remains the key investment constraint.",
            "Sources:",
            url,
        ]
    )


def _social_story(index: int, title: str, body: str, url: str) -> str:
    return "\n".join(
        [
            f"Topic {index}: {title}",
            f"Hook: {body}",
            "Define the Issue: The development remains proposed.",
            "Describe the Situation: Details are based on the supplied evidence.",
            "So Why Does This Matter? It affects project planning.",
            "Call-to-Action: Review the underlying proposal.",
            "Sources:",
            url,
        ]
    )


def _numerical_warnings(warnings: list[str]) -> list[str]:
    return [warning for warning in warnings if "numerical claim" in warning]


def _source_warnings(warnings: list[str]) -> list[str]:
    return [
        warning
        for warning in warnings
        if "source" in warning.casefold() or "publisher URL" in warning
    ]


def test_matching_numerical_claim_produces_no_warning() -> None:
    article = _article(
        "Egypt battery facility",
        "https://publisher.example/battery",
        facts=["The proposed facility has annual assembly capacity of 500 MWh."],
    )
    content = _newsletter_story(
        "Egypt's battery proposal",
        "The proposed facility would have annual capacity of 500 MWh.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_unmatched_numerical_claim_produces_advisory_warning() -> None:
    article = _article(
        "Egypt battery facility",
        "https://publisher.example/battery",
        facts=["The proposed facility has annual assembly capacity of 500 MWh."],
    )
    content = _newsletter_story(
        "Egypt's battery proposal",
        "The proposed facility would have annual capacity of 750 MWh.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert any('numerical claim "750 MWh"' in warning for warning in warnings)
    assert any("possible mismatch" in warning for warning in warnings)


def test_numerical_formatting_differences_are_normalized() -> None:
    article = _article(
        "Iraq solar expansion",
        "https://publisher.example/solar",
        facts=["The proposal would increase capacity from 1000 MW to 2000 MW."],
    )
    content = _social_story(
        1,
        "Iraq solar expansion",
        "Negotiations could increase capacity from 1,000 MW to 2,000 MW.",
        article.canonical_url,
    )

    warnings = validate_social_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_cubic_meter_notation_and_daily_rates_are_normalized() -> None:
    article = _article(
        "Sharjah water infrastructure",
        "https://publisher.example/water",
        facts=["The project will produce 410,000 m³/day."],
    )
    content = _newsletter_story(
        "Sharjah water infrastructure",
        "The project will produce 410000 cubic meters per day.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_cubic_metres_and_superscript_notation_are_normalized() -> None:
    article = _article(
        "Sharjah water infrastructure",
        "https://publisher.example/water",
        facts=["Daily capacity is 410,000 cubic metres."],
    )
    content = _newsletter_story(
        "Sharjah water infrastructure",
        "Daily capacity is 410000 m³.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_hyphenated_and_plural_year_units_are_normalized() -> None:
    article = _article(
        "Sharjah port concession",
        "https://publisher.example/ports",
        facts=["The concession was extended for 35 more years."],
    )
    content = _newsletter_story(
        "A 35-year port concession",
        "The agreement covers 35 years.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_power_and_energy_units_remain_distinct() -> None:
    article = _article(
        "Egypt battery facility",
        "https://publisher.example/battery",
        facts=["The proposed facility has capacity of 500 MWh."],
    )
    content = _newsletter_story(
        "Egypt battery facility",
        "The proposed facility has capacity of 500 MW.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert any('numerical claim "500 MW"' in warning for warning in warnings)


def test_leading_annual_capacity_matches_per_year_evidence() -> None:
    article = _article(
        "Egypt battery facility",
        "https://publisher.example/battery",
        facts=["The facility will assemble 500 MWh per year."],
    )
    content = _newsletter_story(
        "Egypt battery facility",
        "The facility will have annual production capacity of 500 MWh.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_unqualified_unit_can_restate_supported_rated_capacity() -> None:
    article = _article(
        "Egypt battery facility",
        "https://publisher.example/battery",
        facts=["The facility will assemble 500 MWh per year."],
    )
    content = _newsletter_story(
        "Egypt battery facility",
        "The proposed 500 MWh capacity supports local assembly.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_leading_rate_does_not_attach_to_magnitude_words() -> None:
    article = _article(
        "Sharjah trade corridor",
        "https://publisher.example/corridor",
        facts=["The corridor has annual capacity of 1.5 million TEUs."],
    )
    content = _newsletter_story(
        "Sharjah trade corridor",
        "The corridor can handle 1.5 million TEUs annually.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert _numerical_warnings(warnings) == []


def test_daily_and_annual_rates_remain_distinct() -> None:
    article = _article(
        "Water capacity",
        "https://publisher.example/water",
        facts=["The facility produces 500 cubic meters per year."],
    )
    content = _newsletter_story(
        "Water capacity",
        "The facility produces 500 m³/day.",
        article.canonical_url,
    )

    warnings = validate_newsletter_draft(content, [article])

    assert any('numerical claim "500 m³/day"' in warning for warning in warnings)


def test_numbers_cannot_be_justified_by_a_different_story() -> None:
    battery = _article(
        "Egypt battery facility",
        "https://publisher.example/battery",
        facts=["Proposed annual assembly capacity is 500 MWh."],
    )
    solar = _article(
        "Iraq solar expansion",
        "https://publisher.example/solar",
        facts=["The proposal would increase capacity to 2,000 MW."],
    )
    content = "\n".join(
        [
            _newsletter_story(
                "Egypt battery proposal",
                "The battery facility would provide 2,000 MW of capacity.",
                battery.canonical_url,
            ),
            _newsletter_story(
                "Iraq solar proposal",
                "The solar proposal would increase capacity to 2,000 MW.",
                solar.canonical_url,
            ),
        ]
    )

    warnings = validate_newsletter_draft(content, [battery, solar])

    number_warnings = _numerical_warnings(warnings)
    assert len(number_warnings) == 1
    assert "Newsletter story 1" in number_warnings[0]
    assert "Newsletter story 2" not in number_warnings[0]


def test_missing_research_notes_and_story_section_are_reported() -> None:
    legacy = _article(
        "Legacy Sharjah water story",
        "https://publisher.example/water",
        facts=[],
        summary="Sharjah announced planned water infrastructure.",
        status="",
    )

    warnings = validate_newsletter_draft("Weekly introduction only.", [legacy])

    assert any("Research Notes are missing" in warning for warning in warnings)
    assert any("missing story section" in warning for warning in warnings)


def test_missing_and_unresolved_publisher_urls_are_reported() -> None:
    missing = _article(
        "Missing source",
        "",
        facts=["The project remains proposed."],
    )
    google = _article(
        "Unresolved source",
        "https://news.google.com/rss/articles/example",
        facts=["The project remains proposed."],
    )
    content = "\n".join(
        [
            _social_story(1, "Missing source", "The project remains proposed.", ""),
            _social_story(
                2,
                "Unresolved source",
                "The project remains proposed.",
                google.canonical_url,
            ),
        ]
    )

    warnings = validate_social_draft(content, [missing, google])

    assert any("no publisher source URL is available" in warning for warning in warnings)
    assert any("publisher URL remains an unresolved Google News link" in warning for warning in warnings)
    assert any("draft cites an unresolved Google News URL" in warning for warning in warnings)


def test_sns_sources_on_same_line_match_actual_generated_format() -> None:
    article = _article(
        "Egypt battery facility",
        "https://publisher.example/battery",
        facts=["The proposed facility has capacity of 500 MWh."],
    )
    content = "\n".join(
        [
            "Topic 1: Egypt battery facility",
            "Hook: Egypt plans a battery facility.",
            "Define the Issue: Storage supports the grid.",
            "Describe the Situation: The project remains proposed.",
            "So Why Does This Matter? It may strengthen local supply chains.",
            "Call-to-Action: Track the project.",
            f"Sources: Test Publisher, {article.canonical_url}",
        ]
    )

    warnings = validate_social_draft(content, [article])

    assert _source_warnings(warnings) == []


def test_sns_source_supports_blank_lines_and_markdown_links() -> None:
    article = _article(
        "Sharjah water project",
        "https://publisher.example/water",
        facts=["The project remains planned."],
    )
    content = "\n".join(
        [
            "Topic 1: Sharjah water project",
            "Hook: Sharjah plans additional water infrastructure.",
            "Define the Issue: Water security supports growth.",
            "Describe the Situation: The project remains planned.",
            "So Why Does This Matter? It affects long-term water supply.",
            "Call-to-Action: Review delivery milestones.",
            "Sources:",
            "",
            f"[Test Publisher]({article.canonical_url})",
        ]
    )

    warnings = validate_social_draft(content, [article])

    assert _source_warnings(warnings) == []


def test_missing_sns_source_is_reported() -> None:
    article = _article(
        "Missing source",
        "https://publisher.example/missing",
        facts=["The project remains proposed."],
    )
    content = "\n".join(
        [
            "Topic 1: Missing source",
            "Hook: A project was proposed.",
            "Define the Issue: Details remain limited.",
            "Describe the Situation: The proposal is under review.",
            "So Why Does This Matter? Delivery remains uncertain.",
            "Call-to-Action: Verify the proposal.",
        ]
    )

    warnings = validate_social_draft(content, [article])

    assert any("missing Sources section" in warning for warning in warnings)
    assert any("missing source URL" in warning for warning in warnings)


def test_wrong_sns_source_url_is_reported() -> None:
    article = _article(
        "Wrong source",
        "https://publisher.example/correct",
        facts=["The project remains proposed."],
    )
    content = _social_story(
        1,
        "Wrong source",
        "The project remains proposed.",
        "https://publisher.example/wrong",
    )

    warnings = validate_social_draft(content, [article])

    assert any("supplied publisher URL is missing or altered" in warning for warning in warnings)


def test_sns_story_cannot_borrow_another_storys_source() -> None:
    first = _article(
        "First story",
        "https://publisher.example/first",
        facts=["The first project remains proposed."],
    )
    second = _article(
        "Second story",
        "https://publisher.example/second",
        facts=["The second project remains proposed."],
    )
    content = "\n".join(
        [
            _social_story(
                1,
                "First story",
                "The first project remains proposed.",
                second.canonical_url,
            ),
            _social_story(
                2,
                "Second story",
                "The second project remains proposed.",
                second.canonical_url,
            ),
        ]
    )

    warnings = validate_social_draft(content, [first, second])

    altered = [
        warning
        for warning in warnings
        if "supplied publisher URL is missing or altered" in warning
    ]
    assert len(altered) == 1
    assert "SNS story 1" in altered[0]


def test_missing_duplicate_and_unverified_images_are_reported() -> None:
    missing = _article("Missing image", "https://publisher.example/missing")
    first = _article("First image", "https://publisher.example/first")
    first.image_url = "https://images.example.com/shared.jpg?w=1200"
    first.image_provider = "unsplash"
    duplicate = _article("Duplicate image", "https://publisher.example/duplicate")
    duplicate.image_url = "https://images.example.com/shared.jpg?w=800"
    duplicate.image_provider = "brave"

    warnings = validate_newsletter_images([missing, first, duplicate])

    assert any("no usable story image" in warning for warning in warnings)
    assert any("image duplicates Newsletter story 2" in warning for warning in warnings)
    assert any("Unsplash stock image is illustrative" in warning for warning in warnings)
    assert any("Brave image-search result" in warning for warning in warnings)

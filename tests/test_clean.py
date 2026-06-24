from research_automation.pipeline.clean import clean_text


def test_clean_text_normalizes_whitespace() -> None:
    assert clean_text("  One\n\n  two\tthree  ") == "One two three"


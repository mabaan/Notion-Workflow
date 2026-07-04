from research_automation.utils.edition_numbers import next_newsletter_edition, parse_newsletter_code


def test_parse_newsletter_code() -> None:
    assert parse_newsletter_code("NL097") == 97
    assert parse_newsletter_code("bad") is None


def test_next_newsletter_code_parsing() -> None:
    edition = next_newsletter_edition(["NL001", "NL096", "bad-value"])
    assert edition.number == 97
    assert edition.code == "NL097"
    assert edition.title == "Newsletter [97th Edition]"

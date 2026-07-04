from research_automation.utils.urls import clean_url, hostname_matches, url_hostname


def test_clean_url_removes_tracking_params() -> None:
    assert (
        clean_url(
            "HTTPS://Example.com/path/?utm_source=x&utm_medium=y&keep=1&fbclid=abc"
        )
        == "https://example.com/path?keep=1"
    )


def test_url_hostname_normalizes_www() -> None:
    assert url_hostname("https://www.Example.com/path") == "example.com"


def test_hostname_matches_subdomains() -> None:
    assert hostname_matches("www.reuters.com", "reuters.com")
    assert hostname_matches("static.agbi.com", "agbi.com")

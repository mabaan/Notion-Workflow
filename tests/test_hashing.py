from research_automation.utils.hashing import build_content_hash, build_url_hash


def test_url_hash_is_stable() -> None:
    url = "https://example.com/story"
    assert build_url_hash(url) == build_url_hash(url)


def test_content_hash_is_stable() -> None:
    assert build_content_hash(" A Title ", "Reuters") == build_content_hash(
        "A   Title",
        "reuters",
    )

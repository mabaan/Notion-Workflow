from research_automation.models.draft import DraftArticle
from research_automation.pipeline.images import (
    _best_unsplash_image_result,
    inject_story_images,
    markdown_image_match,
)


def test_best_unsplash_image_result_prefers_regular_url() -> None:
    results = [
        {
            "urls": {
                "thumb": "https://example.com/thumb.jpg",
                "regular": "https://example.com/regular.jpg",
            }
        }
    ]

    assert _best_unsplash_image_result(results) == "https://example.com/regular.jpg"


def test_markdown_image_match_parses_external_url() -> None:
    assert markdown_image_match("![Story image](https://example.com/image.jpg)") == (
        "Story image",
        "https://example.com/image.jpg",
    )


def test_inject_story_images_inserts_before_story_headings() -> None:
    content = "\n".join(
        [
            "Welcome",
            "## First story",
            "Body one",
            "## Second story",
            "Body two",
        ]
    )
    articles = [
        DraftArticle(
            title="First story",
            source_name="Example",
            canonical_url="https://example.com/1",
            image_url="https://example.com/1.jpg",
        ),
        DraftArticle(
            title="Second story",
            source_name="Example",
            canonical_url="https://example.com/2",
            image_url="https://example.com/2.jpg",
        ),
    ]

    updated = inject_story_images(content, articles)

    assert "![First story](https://example.com/1.jpg)\n## First story" in updated
    assert "![Second story](https://example.com/2.jpg)\n## Second story" in updated

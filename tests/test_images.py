from pathlib import Path

from research_automation.config import Settings
from research_automation.models.draft import DraftArticle
from research_automation.pipeline.images import (
    ArticleImageResolver,
    _best_unsplash_image_result,
    image_identity,
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


def test_inject_story_images_inserts_after_story_headings_and_tags() -> None:
    content = "\n".join(
        [
            "Welcome",
            "## First story",
            "#FoodandWaterSecurity #Resilience",
            "Body one",
            "## Second story",
            "#NetZeroTransition",
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

    assert (
        "## First story\n#FoodandWaterSecurity #Resilience\n"
        "![First story](https://example.com/1.jpg)\nBody one"
    ) in updated
    assert (
        "## Second story\n#NetZeroTransition\n"
        "![Second story](https://example.com/2.jpg)\nBody two"
    ) in updated


def test_inject_story_images_inserts_after_story_heading_when_no_tags_present() -> None:
    content = "\n".join(
        [
            "Welcome",
            "## First story",
            "Body one",
        ]
    )
    articles = [
        DraftArticle(
            title="First story",
            source_name="Example",
            canonical_url="https://example.com/1",
            image_url="https://example.com/1.jpg",
        )
    ]

    updated = inject_story_images(content, articles)

    assert "## First story\n![First story](https://example.com/1.jpg)\nBody one" in updated


def test_image_identity_ignores_query_params() -> None:
    assert image_identity("https://images.example.com/story.jpg?w=1200&fit=crop") == (
        "https://images.example.com/story.jpg"
    )


def test_resolve_articles_avoids_duplicate_images(monkeypatch, tmp_path: Path) -> None:
    resolver = ArticleImageResolver(
        Settings(
            local_state_path=tmp_path,
            image_discovery_providers=("unsplash",),
        )
    )

    monkeypatch.setattr(
        resolver,
        "_unsplash_image_candidates",
        lambda article: [
            "https://images.example.com/shared.jpg?w=1200",
            f"https://images.example.com/{article.canonical_url.rsplit('/', 1)[-1]}.jpg",
        ],
    )

    articles = [
        DraftArticle(
            title="First story",
            source_name="Example",
            canonical_url="https://example.com/first",
        ),
        DraftArticle(
            title="Second story",
            source_name="Example",
            canonical_url="https://example.com/second",
        ),
    ]

    resolver.resolve_articles(articles)

    assert articles[0].image_url == "https://images.example.com/shared.jpg?w=1200"
    assert articles[1].image_url == "https://images.example.com/second.jpg"

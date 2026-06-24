from research_automation.models.article import Article
from research_automation.pipeline.deduplicate import deduplicate_articles


def test_deduplicate_articles_removes_duplicate_urls() -> None:
    articles = [
        Article(url="https://example.com/a", title="First"),
        Article(url="https://example.com/a", title="Duplicate"),
        Article(url="https://example.com/b", title="Second"),
    ]

    result = deduplicate_articles(articles)

    assert [article.title for article in result] == ["First", "Second"]


from datetime import UTC, datetime
from pathlib import Path

from research_automation.clients.llm_client import LlmClient
from research_automation.models.article import Article, EnrichedArticle
from research_automation.pipeline.notion_write import create_article_queue_page


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "research_automation" / "prompts"


def _article() -> Article:
    return Article(
        title="Egypt battery assembly facility proposed",
        url="https://news.google.com/rss/articles/example",
        canonical_url="https://publisher.example/egypt-battery",
        source_name="Publisher",
        source_page_id="publisher-1",
        published_date=datetime(2026, 10, 14, tzinfo=UTC),
        snippet="The proposed plant would have annual capacity of 500 MWh.",
        region=["Egypt"],
        topic_focus=["energy transition"],
        url_hash="url-hash",
        content_hash="content-hash",
        url_resolution_status="resolved_redirect",
        evidence_retrieval_status="blocked",
    )


def test_llm_enrichment_falls_back_to_snippet_and_preserves_factual_points(
    monkeypatch,
) -> None:
    client = LlmClient(
        provider="openai",
        model="test-model",
        api_key="test-key",
        prompt_directory=PROMPTS_DIR,
        company_topics=("energy transition",),
    )
    captured = {}

    def generate(prompt: str):
        captured["prompt"] = prompt
        return {
            "summary": "A battery facility is proposed in Egypt.",
            "story_type": "infrastructure_project", "is_new_development": True,
            "why_it_matters": "It would add regional battery capacity.",
            "relevance_score": 5,
            "factual_points": [
                "The facility is proposed, not completed.",
                "Proposed annual capacity is 500 MWh.",
            ],
            "topic": ["energy transition"],
            "region": ["Egypt"],
            "newsletter_angle": "Regional storage manufacturing",
            "sns_hook": "Egypt targets 500 MWh of annual battery capacity.",
        }

    monkeypatch.setattr(client, "_generate_json", generate)

    enriched = client.enrich_article(_article())

    assert "Unavailable. Use the RSS title and snippet only." in captured["prompt"]
    assert "annual capacity of 500 MWh" in captured["prompt"]
    assert enriched.factual_points == [
        "The facility is proposed, not completed.",
        "Proposed annual capacity is 500 MWh.",
    ]


def test_llm_enrichment_uses_extracted_article_content(monkeypatch) -> None:
    article = _article()
    article.evidence_retrieval_status = "extracted"
    article.article_text = (
        "The parties are negotiating an increase in solar capacity from "
        "1,000 MW to 2,000 MW; no final agreement has been signed."
    )
    client = LlmClient(
        provider="openai",
        model="test-model",
        api_key="test-key",
        prompt_directory=PROMPTS_DIR,
    )
    captured = {}

    def generate(prompt: str):
        captured["prompt"] = prompt
        return {
            "summary": "Negotiations could double the project's capacity.",
            "story_type": "infrastructure_project", "is_new_development": True,
            "why_it_matters": "The proposal would expand solar generation.",
            "relevance_score": 5,
            "factual_points": [
                "The proposed increase is from 1,000 MW to 2,000 MW."
            ],
        }

    monkeypatch.setattr(client, "_generate_json", generate)

    enriched = client.enrich_article(article)

    assert "1,000 MW to 2,000 MW" in captured["prompt"]
    assert enriched.factual_points == [
        "The proposed increase is from 1,000 MW to 2,000 MW."
    ]


class RecordingNotion:
    def __init__(self) -> None:
        self.properties = None
        self.children = None

    def create_page(self, database_id, properties, children=None):
        self.properties = properties
        self.children = children or []
        return {"id": "article-page"}


def _block_text(block: dict) -> str:
    block_type = block["type"]
    return "".join(
        item.get("text", {}).get("content", "")
        for item in block[block_type].get("rich_text", [])
    )


def test_article_queue_page_contains_concise_research_notes_not_article_body() -> None:
    notion = RecordingNotion()
    article = _article()
    article.evidence_retrieval_status = "extracted"
    article.article_text = "COPYRIGHTED BODY " * 500
    enriched = EnrichedArticle(
        summary="Summary",
        why_it_matters="Why",
        relevance_score=5,
        factual_points=[
            "The facility is proposed with annual capacity of 500 MWh.",
            "Construction has not started.",
        ],
    )

    create_article_queue_page(
        notion,
        "article-db",
        article,
        "dataset-1",
        enriched=enriched,
    )

    texts = [_block_text(block) for block in notion.children]
    assert "Research Notes" in texts
    assert f"Resolved publisher URL: {article.canonical_url}" in texts
    assert "Evidence retrieval status: Extracted" in texts
    assert "The facility is proposed with annual capacity of 500 MWh." in texts
    assert "Construction has not started." in texts
    assert "COPYRIGHTED BODY" not in " ".join(texts)

"""Article enrichment pipeline step."""

from __future__ import annotations

from research_automation.clients.llm_client import LlmClient
from research_automation.models.article import Article, EnrichedArticle


def enrich_article(article: Article, llm_client: LlmClient) -> EnrichedArticle:
    """Enrich an article using the configured LLM client."""

    return llm_client.enrich_article(article)

"""OpenAI-backed LLM helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from research_automation.models.article import Article, EnrichedArticle
from research_automation.utils.evidence import FEED_CONTENT_LIMITATION, is_feed_content


def _render_prompt(template: str, context: dict[str, str]) -> str:
    """Render a small handlebars-like prompt template."""

    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def _coerce_string(value: Any) -> str:
    """Normalize model outputs to strings."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


@dataclass
class LlmClient:
    """Thin OpenAI wrapper for enrichment and weekly drafts."""

    provider: str
    model: str
    api_key: str
    prompt_directory: Path
    company_topics: tuple[str, ...] = ()
    client: OpenAI = field(init=False)

    def __post_init__(self) -> None:
        if self.provider.lower() != "openai":
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is missing.")

        self.client = OpenAI(api_key=self.api_key)

    def enrich_article(self, article: Article) -> EnrichedArticle:
        """Create structured enrichment JSON for an article."""

        prompt = self.render_prompt(
            "article_enrichment.txt",
            {
                "title": article.title,
                "source_name": article.source_name,
                "published_date": article.published_date.isoformat()
                if article.published_date
                else "Unknown",
                "snippet": article.snippet or "No snippet available.",
                "region": ", ".join(article.region) or "Unknown",
                "topic_focus": ", ".join(article.topic_focus) or "Unknown",
                "canonical_url": article.canonical_url or article.url or "Unknown",
                "evidence_retrieval_status": (
                    f"{article.evidence_retrieval_status}: {FEED_CONTENT_LIMITATION}"
                    if is_feed_content(article.evidence_retrieval_status)
                    else article.evidence_retrieval_status
                ),
                "article_content": article.article_text
                or "Unavailable. Use the RSS title and snippet only.",
                "company_topics": ", ".join(self.company_topics) or "Unknown",
                "geographic_scope": (
                    "MENA, GCC, UAE, Saudi Arabia/KSA, Egypt, and genuinely global "
                    "systemic developments with clear relevance to those regions."
                ),
            },
        )
        payload = self._generate_json(prompt)

        relevance_score = _bounded_score(payload.get("relevance_score"), default=1)
        editorial_significance = _bounded_score(
            payload.get("editorial_significance"),
            default=1,
        )

        return EnrichedArticle(
            summary=_coerce_string(payload.get("summary")).strip(),
            why_it_matters=_coerce_string(payload.get("why_it_matters")).strip(),
            relevance_score=relevance_score,
            topic=self._string_list(payload.get("topic")),
            region=self._string_list(payload.get("region")),
            newsletter_angle=_coerce_string(payload.get("newsletter_angle")).strip(),
            sns_hook=_coerce_string(payload.get("sns_hook")).strip(),
            factual_points=self._string_list(payload.get("factual_points"))[:8],
            editorial_significance=editorial_significance,
            significance_reason=_coerce_string(
                payload.get("significance_reason")
            ).strip(),
        )

    def generate_newsletter_draft(
        self,
        week_start: str,
        week_end: str,
        articles: str,
    ) -> str:
        """Generate the newsletter draft body."""

        prompt = self.render_prompt(
            "newsletter_draft.txt",
            {
                "week_start": week_start,
                "week_end": week_end,
                "articles": articles,
            },
        )
        return self._generate_text(prompt)

    def generate_social_media_draft(
        self,
        week_start: str,
        week_end: str,
        articles: str,
    ) -> str:
        """Generate the social media draft body."""

        prompt = self.render_prompt(
            "social_media_draft.txt",
            {
                "week_start": week_start,
                "week_end": week_end,
                "articles": articles,
            },
        )
        return self._generate_text(prompt)

    def render_prompt(self, filename: str, context: dict[str, str]) -> str:
        """Load and render a prompt file."""

        template_path = self.prompt_directory / filename
        template = template_path.read_text(encoding="utf-8")
        return _render_prompt(template, context)

    def _generate_json(self, prompt: str) -> dict[str, Any]:
        """Request a JSON object from the model."""

        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            **self._generation_parameters(temperature=0.2),
            messages=[
                {
                    "role": "system",
                    "content": "Return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = _coerce_string(response.choices[0].message.content).strip()
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Failed to parse JSON response from OpenAI.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("OpenAI JSON response was not an object.")

        return parsed

    def _generate_text(self, prompt: str) -> str:
        """Request plain text content from the model."""

        response = self.client.chat.completions.create(
            model=self.model,
            **self._generation_parameters(temperature=0.4),
            messages=[
                {
                    "role": "system",
                    "content": "Write polished markdown and use only the supplied facts.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = _coerce_string(response.choices[0].message.content).strip()
        if not content:
            raise ValueError("OpenAI returned an empty response.")
        return content

    def _generation_parameters(self, *, temperature: float) -> dict[str, Any]:
        """Use supported reasoning without incompatible sampling parameters."""

        if self.model in {"gpt-6-luna", "gpt-6-sol"}:
            return {"reasoning_effort": "medium"}
        return {"temperature": temperature}

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        """Normalize a model field to a list of strings."""

        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            text = _coerce_string(item).strip()
            if text:
                cleaned.append(text)
        return cleaned


def _bounded_score(value: Any, *, default: int) -> int:
    """Coerce an LLM score to the supported one-to-five range."""

    try:
        score = int(value)
    except (TypeError, ValueError):
        score = default
    return max(1, min(5, score))

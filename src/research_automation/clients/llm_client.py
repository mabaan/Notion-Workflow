"""OpenAI-backed LLM helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from research_automation.models.article import Article, EnrichedArticle


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
            },
        )
        payload = self._generate_json(prompt)

        score = payload.get("relevance_score", 1)
        try:
            relevance_score = int(score)
        except (TypeError, ValueError):
            relevance_score = 1
        relevance_score = max(1, min(5, relevance_score))

        return EnrichedArticle(
            summary=_coerce_string(payload.get("summary")).strip(),
            why_it_matters=_coerce_string(payload.get("why_it_matters")).strip(),
            relevance_score=relevance_score,
            topic=self._string_list(payload.get("topic")),
            region=self._string_list(payload.get("region")),
            newsletter_angle=_coerce_string(payload.get("newsletter_angle")).strip(),
            sns_hook=_coerce_string(payload.get("sns_hook")).strip(),
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
            temperature=0.2,
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
            temperature=0.4,
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

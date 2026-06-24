"""Draft generation pipeline step."""

from __future__ import annotations

from dataclasses import dataclass

from research_automation.models.article import Article
from research_automation.models.draft import Draft


@dataclass(frozen=True)
class DraftRequest:
    """Input data for a draft generation run."""

    title: str
    articles: list[Article]


def generate_draft(request: DraftRequest) -> Draft:
    """Generate a simple draft from articles."""

    lines = [f"# {request.title}", ""]
    if request.articles:
        lines.extend(f"- {article.title or article.url}" for article in request.articles)
    else:
        lines.append("_No articles collected yet._")
    return Draft(title=request.title, content="\n".join(lines))


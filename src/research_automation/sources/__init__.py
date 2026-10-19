"""Article source adapters."""

from research_automation.sources.base import ArticleSource

from research_automation.sources.rss import RssSource

__all__ = ["ArticleSource", "RssSource"]

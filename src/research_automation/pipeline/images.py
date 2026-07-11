"""Image discovery helpers for newsletter drafting."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from research_automation.clients.brave_search_client import BraveSearchClient
from research_automation.clients.discovery_common import (
    ProviderError,
    ProviderLimitError,
)
from research_automation.config import Settings
from research_automation.clients.unsplash_client import UnsplashClient
from research_automation.models.draft import DraftArticle
from research_automation.utils.hashing import build_url_hash
from research_automation.utils.urls import clean_url, hostname_matches, url_hostname

logger = logging.getLogger(__name__)

IMAGE_MARKDOWN_RE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<url>[^)]+)\)$")


@dataclass
class ArticleAssetStore:
    """Simple JSON cache keyed by canonical URL hash."""

    path: Path

    def __post_init__(self) -> None:
        self.records = self._load()

    def get_image_url(self, canonical_url: str) -> str:
        key = build_url_hash(clean_url(canonical_url))
        return str(self.records.get(key, {}).get("image_url") or "")

    def get_provider(self, canonical_url: str) -> str:
        """Return the cached image provider for a canonical URL."""

        key = build_url_hash(clean_url(canonical_url))
        return str(self.records.get(key, {}).get("provider") or "")

    def record_image_url(
        self,
        *,
        canonical_url: str,
        image_url: str,
        provider: str,
    ) -> None:
        key = build_url_hash(clean_url(canonical_url))
        self.records[key] = {
            "canonical_url": clean_url(canonical_url),
            "image_url": clean_url(image_url),
            "provider": provider,
        }
        self._save()

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}

        contents = self.path.read_text(encoding="utf-8").strip()
        if not contents:
            return {}

        payload = json.loads(contents)
        if not isinstance(payload, dict):
            raise ValueError(f"Article asset store at {self.path} must be a JSON object.")
        return payload

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.records, indent=2, sort_keys=True),
            encoding="utf-8",
        )


@dataclass
class ArticleImageResolver:
    """Resolve story images with provider fallback and local caching."""

    settings: Settings

    def __post_init__(self) -> None:
        self.store = ArticleAssetStore(self.settings.article_assets_path)
        self.unsplash = (
            UnsplashClient(self.settings.unsplash_access_key)
            if self.settings.unsplash_access_key
            else None
        )
        self.brave = (
            BraveSearchClient(self.settings.brave_search_api_key)
            if self.settings.brave_search_api_key
            else None
        )
        self.unsplash_requests = 0
        self.brave_requests = 0

    def resolve_articles(self, articles: list[DraftArticle]) -> list[DraftArticle]:
        """Resolve image URLs for supplied draft articles."""

        used_image_ids: set[str] = set()
        for article in articles:
            existing_image = clean_url(article.image_url)
            existing_image_id = image_identity(existing_image)
            if existing_image and existing_image_id and existing_image_id not in used_image_ids:
                article.image_url = existing_image
                used_image_ids.add(existing_image_id)
                continue

            article.image_url = self.resolve_image(
                article,
                excluded_image_ids=used_image_ids,
            )
            resolved_image_id = image_identity(article.image_url)
            if resolved_image_id:
                used_image_ids.add(resolved_image_id)
        return articles

    def resolve_image(
        self,
        article: DraftArticle,
        *,
        excluded_image_ids: set[str] | None = None,
    ) -> str:
        """Resolve a single article image URL."""

        excluded_image_ids = excluded_image_ids or set()
        cached = self.store.get_image_url(article.canonical_url)
        cached_provider = self.store.get_provider(article.canonical_url).casefold()
        allowed_cache_providers = {
            provider.casefold() for provider in self.settings.image_discovery_providers
        }
        cached_identity = image_identity(cached)
        if (
            cached
            and cached_provider in allowed_cache_providers
            and cached_identity not in excluded_image_ids
        ):
            return cached

        for provider in self.settings.image_discovery_providers:
            provider_name = provider.casefold()

            try:
                if provider_name == "unsplash":
                    candidate_urls = self._unsplash_image_candidates(article)
                elif provider_name == "brave":
                    candidate_urls = self._brave_image_candidates(article)
                else:
                    logger.info("Skipping unknown image provider: %s", provider)
                    continue
            except ProviderLimitError as exc:
                logger.warning("Image provider quota unavailable for %s: %s", provider, exc)
                continue
            except ProviderError as exc:
                logger.warning("Image provider failed for %s: %s", article.title, exc)
                continue

            for image_url in candidate_urls:
                image_id = image_identity(image_url)
                if image_id and image_id in excluded_image_ids:
                    continue
                self.store.record_image_url(
                    canonical_url=article.canonical_url,
                    image_url=image_url,
                    provider=provider_name,
                )
                return image_url

        return ""

    def _unsplash_image_candidates(self, article: DraftArticle) -> list[str]:
        if self.unsplash is None:
            return []

        self.unsplash_requests += 1
        queries = _unsplash_queries(article)
        candidates: list[str] = []
        for query in queries:
            results = self.unsplash.search_photos(query=query, per_page=5)
            candidates.extend(_unsplash_image_results(results))
        return _unique_image_urls(candidates)

    def _brave_image_candidates(self, article: DraftArticle) -> list[str]:
        if self.brave is None or self.brave_requests >= self.settings.brave_max_requests_per_run:
            return []

        self.brave_requests += 1
        query = f"{article.title} {article.source_name}".strip()
        language = "en"
        results = self.brave.search_images(query=query, count=5, search_lang=language)
        return _image_result_candidates(
            results,
            article.canonical_url,
            "url",
            "properties",
        )


def inject_story_images(content: str, articles: list[DraftArticle]) -> str:
    """Insert one markdown image line after each story heading and tag line."""

    lines = content.splitlines()
    headings = [index for index, line in enumerate(lines) if line.startswith("## ")]
    if not headings:
        return content

    offset = 0
    for article_index, heading_index in enumerate(headings):
        if article_index >= len(articles):
            break
        image_url = clean_url(articles[article_index].image_url)
        if not image_url:
            continue
        insert_at = _story_image_insert_index(lines, heading_index + offset)
        lines.insert(
            insert_at,
            f"![{articles[article_index].title}]({image_url})",
        )
        offset += 1

    return "\n".join(lines)


def markdown_image_match(line: str) -> tuple[str, str] | None:
    """Parse one markdown image line."""

    match = IMAGE_MARKDOWN_RE.match(line.strip())
    if not match:
        return None

    alt = match.group("alt").strip()
    url = clean_url(match.group("url"))
    if not url:
        return None
    return alt, url


def _story_image_insert_index(lines: list[str], heading_index: int) -> int:
    """Return the insertion point for a story image."""

    insert_at = heading_index + 1
    while insert_at < len(lines) and _is_tag_line(lines[insert_at]):
        insert_at += 1
    return insert_at


def _is_tag_line(line: str) -> bool:
    """Return True when a line is a hashtag tag row, not a heading."""

    stripped = line.strip()
    return (
        stripped.startswith("#")
        and not stripped.startswith("##")
        and not stripped.startswith("# ")
    )


def image_identity(image_url: str) -> str:
    """Return a duplicate-resistant identifier for an image URL."""

    cleaned = clean_url(image_url)
    if not cleaned:
        return ""

    parts = urlsplit(cleaned)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def _unsplash_queries(article: DraftArticle) -> list[str]:
    queries: list[str] = []

    if article.title.strip():
        queries.append(article.title.strip())

    if article.topic:
        topic_query = " ".join(article.topic[:2]).strip()
        if topic_query and topic_query not in queries:
            queries.append(topic_query)

    if article.region:
        region_query = " ".join(article.region[:2]).strip()
        if region_query and article.topic:
            combined = f"{topic_query} {region_query}".strip()
            if combined and combined not in queries:
                queries.append(combined)

    return queries


def _best_unsplash_image_result(results: list[dict[str, Any]]) -> str:
    image_urls = _unsplash_image_results(results)
    return image_urls[0] if image_urls else ""


def _unsplash_image_results(results: list[dict[str, Any]]) -> list[str]:
    image_urls: list[str] = []
    for result in results:
        urls = result.get("urls")
        if not isinstance(urls, dict):
            continue
        for key in ("regular", "full", "small", "raw"):
            image_url = clean_url(str(urls.get(key) or ""))
            if image_url:
                image_urls.append(image_url)
    return _unique_image_urls(image_urls)


def _best_image_result(
    results: list[dict[str, Any]],
    canonical_url: str,
    page_url_key: str,
    image_key: str,
) -> str:
    image_urls = _image_result_candidates(results, canonical_url, page_url_key, image_key)
    return image_urls[0] if image_urls else ""


def _image_result_candidates(
    results: list[dict[str, Any]],
    canonical_url: str,
    page_url_key: str,
    image_key: str,
) -> list[str]:
    target_host = url_hostname(canonical_url)
    preferred: list[str] = []
    fallback: list[str] = []

    for result in results:
        page_url = clean_url(str(result.get(page_url_key) or result.get("url") or ""))
        image_url = ""
        nested = result.get(image_key)
        if isinstance(nested, dict):
            image_url = clean_url(str(nested.get("url") or ""))
        elif isinstance(nested, str):
            image_url = clean_url(nested)

        if not image_url:
            thumbnail = result.get("thumbnail")
            if isinstance(thumbnail, dict):
                image_url = clean_url(str(thumbnail.get("src") or ""))
            else:
                image_url = clean_url(str(thumbnail or ""))

        if not image_url:
            continue

        if page_url and hostname_matches(url_hostname(page_url), target_host):
            preferred.append(image_url)
        else:
            fallback.append(image_url)

    return _unique_image_urls([*preferred, *fallback])


def _unique_image_urls(image_urls: list[str]) -> list[str]:
    unique_urls: list[str] = []
    seen: set[str] = set()

    for image_url in image_urls:
        image_id = image_identity(image_url)
        if not image_id or image_id in seen:
            continue
        seen.add(image_id)
        unique_urls.append(clean_url(image_url))

    return unique_urls

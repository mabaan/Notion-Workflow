"""Bounded publisher-page retrieval and article text extraction."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from lxml import html as lxml_html
from readability import Document

from research_automation.models.article import Article
from research_automation.utils.text import normalize_whitespace
from research_automation.utils.urls import (
    clean_url,
    hostname_matches,
    is_google_news_url,
    url_hostname,
)


@dataclass(frozen=True)
class ArticleRetrievalResult:
    """Resolved URL and bounded evidence text for one shortlisted article."""

    canonical_url: str
    url_resolution_status: str
    evidence_retrieval_status: str
    article_text: str = ""


@dataclass
class ArticleRetriever:
    """Fetch and extract a shortlisted article without bypassing access controls."""

    client: httpx.Client | None = None
    max_response_bytes: int = 2_000_000
    max_text_chars: int = 12_000
    minimum_text_chars: int = 300

    def retrieve(self, article: Article) -> ArticleRetrievalResult:
        """Return publisher URL and useful article text when publicly accessible."""

        original_url = clean_url(article.canonical_url or article.url)
        if not original_url:
            return ArticleRetrievalResult(
                canonical_url="",
                url_resolution_status="unresolved",
                evidence_retrieval_status="invalid_url",
            )

        if self.client is not None:
            return self._retrieve_with_client(self.client, original_url)

        timeout = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            return self._retrieve_with_client(client, original_url)

    def _retrieve_with_client(
        self,
        client: httpx.Client,
        original_url: str,
    ) -> ArticleRetrievalResult:
        resolution_status = _initial_resolution_status(original_url)
        canonical_url = original_url
        try:
            with client.stream(
                "GET",
                original_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "SOMA-MATER-Research/1.0",
                },
            ) as response:
                final_url = clean_url(str(response.url)) or original_url
                canonical_url, resolution_status = _redirected_publisher_url(
                    original_url,
                    final_url,
                )
                if response.status_code in {401, 402, 403, 407, 429, 451}:
                    return ArticleRetrievalResult(
                        canonical_url=canonical_url,
                        url_resolution_status=resolution_status,
                        evidence_retrieval_status="blocked",
                    )
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").casefold()
                if content_type and not any(
                    value in content_type for value in ("text/html", "application/xhtml+xml")
                ):
                    return ArticleRetrievalResult(
                        canonical_url=canonical_url,
                        url_resolution_status=resolution_status,
                        evidence_retrieval_status="unsupported_content",
                    )

                content_length = _content_length(response)
                if content_length is not None and content_length > self.max_response_bytes:
                    return ArticleRetrievalResult(
                        canonical_url=canonical_url,
                        url_resolution_status=resolution_status,
                        evidence_retrieval_status="too_large",
                    )

                body = _read_bounded(response, self.max_response_bytes)
                encoding = response.encoding or "utf-8"
        except ResponseTooLarge:
            return ArticleRetrievalResult(
                canonical_url=canonical_url,
                url_resolution_status=resolution_status,
                evidence_retrieval_status="too_large",
            )
        except (httpx.HTTPError, ValueError):
            return ArticleRetrievalResult(
                canonical_url=canonical_url,
                url_resolution_status=resolution_status,
                evidence_retrieval_status="fetch_failed",
            )

        html = body.decode(encoding, errors="replace")
        canonical_url, resolution_status = _resolved_canonical_url(
            original_url,
            final_url,
            html,
        )
        extracted = _extract_article_text(html, canonical_url)
        text = normalize_whitespace(extracted or "")
        if len(text) < self.minimum_text_chars:
            return ArticleRetrievalResult(
                canonical_url=canonical_url,
                url_resolution_status=resolution_status,
                evidence_retrieval_status="insufficient_content",
            )

        return ArticleRetrievalResult(
            canonical_url=canonical_url,
            url_resolution_status=resolution_status,
            evidence_retrieval_status="extracted",
            article_text=text[: self.max_text_chars],
        )


class ResponseTooLarge(RuntimeError):
    """Raised when a streamed article exceeds the configured byte ceiling."""


def apply_retrieval_result(
    article: Article,
    result: ArticleRetrievalResult,
) -> None:
    """Apply retrieval output without discarding the original feed-entry URL."""

    article.canonical_url = result.canonical_url or article.canonical_url or article.url
    article.url_resolution_status = result.url_resolution_status
    article.evidence_retrieval_status = result.evidence_retrieval_status
    article.article_text = result.article_text


def _read_bounded(response: httpx.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > max_bytes:
            raise ResponseTooLarge
        chunks.append(chunk)
    return b"".join(chunks)


def _content_length(response: httpx.Response) -> int | None:
    raw = response.headers.get("content-length", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _initial_resolution_status(url: str) -> str:
    return "unresolved" if is_google_news_url(url) else "publisher_url"


def _resolved_canonical_url(
    original_url: str,
    final_url: str,
    html: str,
) -> tuple[str, str]:
    metadata_url = _extract_canonical_url(html, final_url)

    if _is_confident_publisher_url(metadata_url, final_url, original_url):
        status = "resolved_canonical" if metadata_url != original_url else "publisher_url"
        return metadata_url, status
    if _is_confident_publisher_url(final_url, final_url, original_url):
        status = "resolved_redirect" if final_url != original_url else "publisher_url"
        return final_url, status
    return original_url, _initial_resolution_status(original_url)


def _redirected_publisher_url(
    original_url: str,
    final_url: str,
) -> tuple[str, str]:
    if final_url and not is_google_news_url(final_url):
        status = "resolved_redirect" if final_url != original_url else "publisher_url"
        return final_url, status
    return original_url, _initial_resolution_status(original_url)


def _extract_article_text(html: str, url: str) -> str:
    try:
        summary = Document(html, url=url).summary(html_partial=True)
        tree = lxml_html.fromstring(summary)
        return tree.text_content()
    except Exception:
        return ""


def _extract_canonical_url(html: str, base_url: str) -> str:
    try:
        tree = lxml_html.fromstring(html)
        candidates = tree.xpath(
            "//link[contains(concat(' ', normalize-space(translate(@rel, "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')), ' '), "
            "' canonical ')]/@href"
        )
    except Exception:
        return ""
    if not candidates:
        return ""
    return clean_url(urljoin(base_url, str(candidates[0]).strip()))


def _is_confident_publisher_url(
    candidate_url: str,
    final_url: str,
    original_url: str,
) -> bool:
    if not candidate_url or is_google_news_url(candidate_url):
        return False
    candidate_host = url_hostname(candidate_url)
    final_host = url_hostname(final_url)
    original_host = url_hostname(original_url)
    if not candidate_host:
        return False
    if is_google_news_url(original_url):
        return bool(final_host and hostname_matches(candidate_host, final_host))
    return hostname_matches(candidate_host, final_host) or hostname_matches(
        candidate_host,
        original_host,
    )

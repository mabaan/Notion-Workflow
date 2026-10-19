"""Opt-in, bounded Google News decoding immediately before evidence retrieval.

The unofficial protocol can change. Failures always retain the wrapper path;
publisher access and extraction remain the existing ArticleRetriever's job.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import ipaddress
import json
import re
import time
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

import httpx
from lxml import etree, html

from research_automation.pipeline.article_retrieval import ArticleRetrievalResult
from research_automation.utils.urls import clean_url, hostname_matches

# Protocol context adapted from SSujitX/google-news-url-decoder at
# 990bf393f0c0717988c6456c641a2c6af252b599 (MIT).
# Copyright (c) 2024 Sujit Biswas
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
_GART_CONTEXT = [
    ["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
    "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0,
]
_RPC = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
_HEADERS = {"User-Agent": "SOMA-MATER-Research/1.0", "Accept": "text/html,application/json"}
_REFUSED = {401, 402, 403, 405, 407, 429, 451}
_NON_ARTICLE = {"search", "login", "signin", "sign-in", "register", "subscribe", "category",
                "categories", "tags", "tag", "authors", "author", "about", "contact", "privacy", "terms"}


def _hostname(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def is_google_wrapper(url: str) -> bool:
    """Recognize the actual Google host, never a lookalike suffix."""
    return _hostname(url) == "news.google.com"


def _article_id(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname != "news.google.com"
                or parts.username or parts.password or parts.port not in {None, 443}):
            return None
        match = re.fullmatch(r"/(?:rss/articles|articles|read)/([A-Za-z0-9_-]{10,2500})", parts.path)
        return match[1] if match else None
    except ValueError:
        return None


def valid_publisher_destination(url: str, expected_domain: str = "") -> bool:
    """Check public HTTP(S), plausible article paths and registry host metadata."""
    try:
        if not isinstance(url, str) or re.search(r"[\s\\\x00-\x1f]", url):
            return False
        parts = urlsplit(url)
        host = _hostname(url)
        if (parts.scheme not in {"http", "https"} or parts.username or parts.password
                or parts.port not in {None, 80, 443} or "." not in host
                or host.endswith((".local", ".localhost")) or host == "localhost"
                or any(label in {"google", "googleusercontent", "gstatic"} for label in host.split("."))):
            return False
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or ".." in host:
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        if expected_domain and not hostname_matches(host, expected_domain):
            return False
        segments = [s.casefold() for s in unquote(parts.path).split("/") if s]
        if not segments or any(s in _NON_ARTICLE for s in segments):
            return False
        if len(segments) == 1 and segments[0] in {"news", "world", "business", "science", "en", "ar", "home", "index.html"}:
            return False
        if re.search(r"\.(?:jpg|png|gif|svg|js|css|pdf|xml|mp4)$", segments[-1], re.I):
            return False
        return len(re.findall(r"[^\W_]+", segments[-1])) >= 3 or bool(
            set(segments[:-1]) & {"article", "articles", "node", "story", "stories"}
        )
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class GoogleNewsResolutionResult:
    original_url: str
    status: str
    resolved_url: str = ""
    request_count: int = 0
    latency_seconds: float = 0.0
    failure_reason: str = ""
    attempted: bool = False
    cache_hit: bool = False
    http_429_count: int = 0


class _ResolutionFailure(Exception):
    """Only controlled categories, never payloads or transport exceptions."""


def _signature(markup: str) -> tuple[str, str]:
    try:
        tree = html.fromstring(markup)
        pairs = {(n.get("data-n-a-sg"), n.get("data-n-a-ts"))
                 for n in tree.xpath("//*[@data-n-a-sg and @data-n-a-ts]")}
        if len(pairs) == 1:
            signature, stamp = pairs.pop()
            if signature and len(signature) <= 4096 and re.fullmatch(r"\d{1,16}", stamp or ""):
                return signature, stamp
    except (ValueError, etree.LxmlError):
        pass
    raise _ResolutionFailure("signature_or_timestamp_missing")


def _rpc_url(body: str) -> str:
    value = body.lstrip("\ufeff \r\n\t")
    if value.startswith(")]}'"):
        value = value[4:].lstrip()
    decoder, urls = json.JSONDecoder(), []
    while value:
        frame = re.match(r"^\d+\s*\n", value)
        if frame:
            value = value[frame.end():].lstrip()
            continue
        rows, end = decoder.raw_decode(value)
        value = value[end:].lstrip()
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list) or len(row) < 3 or row[:2] != ["wrb.fr", "Fbv4je"]:
                continue
            payload = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            if isinstance(payload, list) and len(payload) > 1 and payload[0] == "garturlres" and isinstance(payload[1], str):
                urls.append(payload[1])
    if len(urls) != 1:
        raise _ResolutionFailure("missing_or_ambiguous_rpc_url")
    return urls[0]


def _challenge(markup: str) -> bool:
    try:
        tree = html.fromstring(markup or "<html></html>")
        title = " ".join(tree.xpath("//title/text()|//h1//text()"))
        return bool(re.search(r"unusual traffic|before you continue|access denied|verify.{0,20}human|captcha|just a moment|^sorry", title, re.I)
                    or tree.xpath('//form[contains(@action,"/sorry/")]'))
    except (ValueError, etree.LxmlError):
        return False


class GoogleNewsResolver:
    """One serial attempt per normalized wrapper; cache and refusal latch per run."""

    def __init__(self, client: httpx.Client | None = None, *, max_attempts=48, sleep=time.sleep, clock=time.monotonic):
        self.client, self.sleep, self.clock = client, sleep, clock
        self.max_attempts, self.attempt_count = max_attempts, 0
        self.cache: dict[str, GoogleNewsResolutionResult] = {}
        self.stopped_reason = ""
        self.last_request_at: float | None = None

    def resolve(self, original_url: str, expected_domain: str = "") -> GoogleNewsResolutionResult:
        if not is_google_wrapper(original_url):
            return GoogleNewsResolutionResult(original_url, "not_google_news")
        if not _article_id(original_url):
            return GoogleNewsResolutionResult(original_url, "resolution_failed", failure_reason="invalid_google_wrapper")
        key = clean_url(original_url)
        if key in self.cache:
            result = replace(self.cache[key], original_url=original_url, request_count=0,
                             latency_seconds=0.0, attempted=False, cache_hit=True, http_429_count=0)
        elif self.stopped_reason:
            result = GoogleNewsResolutionResult(original_url,
                "rate_limited" if self.stopped_reason == "google_http_429" else "resolution_failed",
                failure_reason="stopped_after_" + self.stopped_reason)
            self.cache[key] = result
        elif self.attempt_count >= self.max_attempts:
            result = GoogleNewsResolutionResult(original_url, "resolution_failed",
                                                failure_reason="resolution_attempt_budget_exhausted")
            self.cache[key] = result
        else:
            self.attempt_count += 1
            if self.client is not None:
                result = self._resolve(self.client, original_url)
            else:
                # No environment proxy, redirects, network retries or persistent client.
                with httpx.Client(trust_env=False, follow_redirects=False, timeout=15.0) as client:
                    result = self._resolve(client, original_url)
            self.cache[key] = result
        # Revalidate cached destinations against this candidate's source metadata.
        if result.status == "resolved" and not valid_publisher_destination(result.resolved_url, expected_domain):
            return replace(result, status="invalid_destination", resolved_url="", failure_reason="invalid_or_wrong_publisher_url")
        return result

    def _resolve(self, client: httpx.Client, url: str) -> GoogleNewsResolutionResult:
        started, requests, limited = self.clock(), 0, 0

        def request(method, target, *, content=None):
            nonlocal requests, limited
            if self.last_request_at is not None:
                self.sleep(max(0.0, 2.0 - (self.clock() - self.last_request_at)))
            self.last_request_at = self.clock()
            requests += 1
            headers = dict(_HEADERS)
            if method == "POST":
                headers["Content-Type"] = "application/x-www-form-urlencoded;charset=UTF-8"
            with client.stream(method, target, content=content, headers=headers,
                               follow_redirects=False, timeout=15.0) as response:
                if response.status_code in _REFUSED:
                    limited += int(response.status_code == 429)
                    self.stopped_reason = "google_http_429" if limited else "google_http_refusal"
                    raise _ResolutionFailure(self.stopped_reason)
                if response.status_code >= 400:
                    raise _ResolutionFailure("google_http_error")
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > 2_000_000:
                        raise _ResolutionFailure("google_response_too_large")
                    body.extend(chunk)
                markup = body.decode("utf-8", errors="replace")
                if _challenge(markup):
                    self.stopped_reason = "google_challenge_or_consent"
                    raise _ResolutionFailure(self.stopped_reason)
                return response.status_code, response.headers, markup

        resolved, status, reason = "", "resolution_failed", ""
        try:
            identity = _article_id(url)
            query = parse_qs(urlsplit(url).query)
            locale = {k: query.get(k, [default])[0] for k, default in
                      (("hl", "en-US"), ("gl", "US"), ("ceid", "US:en"))}
            current = "https://news.google.com/rss/articles/" + identity + "?" + urlencode(locale)
            for hop in range(2):
                code, headers, markup = request("GET", current)
                if not 300 <= code < 400:
                    break
                destination = urljoin(current, headers.get("location", ""))
                if valid_publisher_destination(destination):
                    resolved = destination
                    break
                if _hostname(destination) in {"google.com", "consent.google.com", "accounts.google.com"} or "/sorry" in destination:
                    self.stopped_reason = "google_challenge_or_consent"
                    raise _ResolutionFailure(self.stopped_reason)
                if hop or _article_id(destination) != identity:
                    raise _ResolutionFailure("unexpected_google_redirect")
                current = destination
            if not resolved:
                signature, stamp = _signature(markup)
                inner = ["garturlreq", _GART_CONTEXT, identity, int(stamp), signature]
                envelope = [[["Fbv4je", json.dumps(inner, separators=(",", ":")), None, "0"]]]
                content = urlencode({"f.req": json.dumps(envelope, separators=(",", ":"))})
                code, _, body = request("POST", _RPC, content=content)
                if 300 <= code < 400:
                    self.stopped_reason = "google_rpc_redirect_refused"
                    raise _ResolutionFailure(self.stopped_reason)
                resolved = _rpc_url(body)
            if valid_publisher_destination(resolved):
                status = "resolved"
                resolved = clean_url(resolved)
            else:
                status, resolved, reason = "invalid_destination", "", "invalid_or_wrong_publisher_url"
        except _ResolutionFailure as exc:
            reason = str(exc)
        except httpx.TimeoutException:
            reason = "google_timeout"
        except httpx.HTTPError:
            reason = "google_http_or_network_error"
        except (ValueError, TypeError, IndexError, KeyError, RecursionError):
            reason = "malformed_rpc_response"
        return GoogleNewsResolutionResult(url, "rate_limited" if limited else status,
            resolved_url=resolved, request_count=requests,
            latency_seconds=round(max(0.0, self.clock() - started), 3),
            failure_reason=reason, attempted=True, http_429_count=limited)


class GoogleNewsResolvingRetriever:
    """Decorate the existing retrieval callback, never collection/classification."""

    def __init__(self, retrieve, sources, *, resolver: GoogleNewsResolver | None = None,
                 max_resolution_attempts: int = 48):
        self.retrieve = retrieve
        self.resolver = resolver or GoogleNewsResolver(max_attempts=max_resolution_attempts)
        self.domains = {s.notion_page_id: _hostname(s.source_url) for s in sources
                        if s.notion_page_id and s.source_url}

    def __call__(self, article) -> ArticleRetrievalResult:
        wrapper = article.canonical_url or article.url
        if not is_google_wrapper(wrapper):
            return self.retrieve(article)
        expected = self.domains.get(article.source_page_id, "")
        try:
            result = self.resolver.resolve(wrapper, expected)
            if result.status == "resolved" and not valid_publisher_destination(result.resolved_url, expected):
                result = replace(result, status="invalid_destination", resolved_url="", failure_reason="invalid_or_wrong_publisher_url")
        except Exception:
            # Unexpected decoder failure must not prevent normal evidence assessment.
            result = GoogleNewsResolutionResult(wrapper, "resolution_failed", failure_reason="resolver_error", attempted=True)
        article.google_news_resolution = {
            "original_acquisition_method": article.discovery_method or (
                "discovery_fallback" if article.discovery_provider else "google_news_rss"),
            "original_wrapper_url": wrapper,
            "expected_publisher_hostname": expected,
            "attempted": result.attempted, "status": result.status,
            "resolved_hostname": _hostname(result.resolved_url),
            "request_count": result.request_count, "latency_seconds": result.latency_seconds,
            "failure_reason": result.failure_reason, "cache_hit": result.cache_hit,
            "http_429_count": result.http_429_count,
            "evidence_status_before": article.evidence_retrieval_status,
        }
        article.canonical_url = result.resolved_url if result.status == "resolved" else wrapper
        if result.status == "resolved":
            article.url_resolution_status = "resolved_google_news"
        try:
            retrieved = self.retrieve(article)
        except Exception:
            article.google_news_resolution["evidence_status_after"] = "fetch_failed"
            raise  # Existing caller handles retrieval failure and still enriches.
        article.google_news_resolution["evidence_status_after"] = retrieved.evidence_retrieval_status
        if result.status == "resolved":
            retrieved = replace(retrieved, url_resolution_status="resolved_google_news")
        return retrieved

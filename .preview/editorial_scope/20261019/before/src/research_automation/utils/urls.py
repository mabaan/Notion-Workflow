"""URL normalization helpers for feed entries."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_HREF_RE = re.compile(r'href=[\'"](?P<url>[^\'"]+)[\'"]', re.IGNORECASE)

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def clean_url(raw_url: str) -> str:
    """Normalize a URL for deduplication and storage."""

    url = raw_url.strip()
    if not url:
        return ""

    if "://" not in url:
        url = f"https://{url}"

    parts = urlsplit(url)
    scheme = parts.scheme.lower() or "https"
    hostname = (parts.hostname or "").lower().rstrip(".")
    port = parts.port

    netloc = hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_PARAMS and not key.casefold().startswith("utm_")
    ]
    query = urlencode(sorted(filtered_query), doseq=True)

    path = parts.path or ""
    if path not in {"", "/"} and path.endswith("/"):
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, query, ""))


def url_hostname(raw_url: str) -> str:
    """Return a normalized hostname for a URL."""

    cleaned = clean_url(raw_url)
    if not cleaned:
        return ""

    hostname = (urlsplit(cleaned).hostname or "").lower()
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


def hostname_matches(left: str, right: str) -> bool:
    """Return whether two hostnames refer to the same site."""

    normalized_left = left.lower().removeprefix("www.").strip(".")
    normalized_right = right.lower().removeprefix("www.").strip(".")
    if not normalized_left or not normalized_right:
        return False
    return (
        normalized_left == normalized_right
        or normalized_left.endswith(f".{normalized_right}")
        or normalized_right.endswith(f".{normalized_left}")
    )


def is_google_news_url(url: str) -> bool:
    """Return whether a URL points at Google News."""

    hostname = urlsplit(url).hostname or ""
    return hostname.endswith("news.google.com")


def extract_entry_url(entry: dict[str, Any]) -> str:
    """Return the best URL for a feed entry."""

    primary_link = str(entry.get("link") or "").strip()
    if primary_link and not is_google_news_url(primary_link):
        return primary_link

    for key in ("feedburner_origlink", "origlink"):
        candidate = str(entry.get(key) or "").strip()
        if candidate:
            return candidate

    for link in entry.get("links", []):
        href = str(link.get("href") or "").strip()
        if href and not is_google_news_url(href):
            return href

    for field_name in ("summary", "description"):
        candidate = _first_non_google_href(str(entry.get(field_name) or ""))
        if candidate:
            return candidate

    return primary_link


def _first_non_google_href(html: str) -> str:
    for match in _HREF_RE.finditer(html):
        candidate = match.group("url").strip()
        if candidate and not is_google_news_url(candidate):
            return candidate
    return ""

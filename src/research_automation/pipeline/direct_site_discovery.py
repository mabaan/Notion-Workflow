"""Bounded, optional listing supplement for four registered publishers.

Static HTTP and DOM rules follow the discovery benchmark, using existing httpx /
lxml dependencies. No article-body retrieval, model, state or Notion operations.
The ingestion caller enforces dry-run-only use during this shadow experiment.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
import re
from time import perf_counter
import unicodedata
from urllib.parse import urljoin, urlsplit

import httpx
from lxml import html

from research_automation.models.article import Article
from research_automation.models.source import Source
from research_automation.pipeline.selection import _event_title
from research_automation.utils.urls import clean_url, is_google_news_url

TARGET_PUBLISHERS = {
    "Arab News": "arabnews.com",
    "Saudi Gazette": "saudigazette.com.sa",
    "Khaleej Times": "khaleejtimes.com",
    "The National": "thenationalnews.com",
}
MAX_CANDIDATE_ANCHORS = 100
MAX_RECENT_ARTICLES = 20
MAX_RESPONSE_BYTES = 2_000_000
HEADERS = {"User-Agent": "SOMA-MATER-Research/1.0", "Accept": "text/html,application/xhtml+xml"}
NON_ARTICLE = re.compile(
    r"^(?:about(?:-us)?|contact(?:-us)?|login|log-in|sign-?in|sign-?up|register|registration|"
    r"newsletters?|subscribe|subscriptions?|search|tags?|authors?|profiles?|categories|category|"
    r"topics?|privacy|terms|advertising|cookies?|account|careers|jobs?|collections?|events?|"
    r"podcasts?|videos?|photos?|pictures?|cartoons?|gallery|galleries|help|faq|sitemap|rss|feeds?)$", re.I,
)
ASSET = re.compile(r"\.(?:jpg|jpeg|png|gif|svg|webp|css|js|pdf|zip|xml|mp4|mp3|woff2?)$", re.I)
RELATIVE_DATE = re.compile(r"(?<!\w)(\d+)\s*(minutes?|mins?|hours?|hrs?|days?|[mhd])\s+ago\b", re.I)
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
VISIBLE_DATE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+" + MONTH + r"\s+\d{4}|" + MONTH + r"\s+\d{1,2},?\s+\d{4})\b", re.I)


@dataclass
class HybridDiscoveryResult:
    articles: list[Article]
    sources: dict[str, dict] = field(default_factory=dict)


def acquisition_method(article: Article) -> str:
    """Explicit for adapters; compatible with older in-memory Article objects."""
    if article.discovery_method:
        return article.discovery_method
    if article.discovery_provider:
        return "discovery_fallback"
    try:
        return "google_news_rss" if is_google_news_url(article.url) else "rss"
    except ValueError:
        return "rss"  # invalid input still needs an objective-cleanup audit


def _text(node) -> str:
    return " ".join(" ".join(node.xpath(".//text()[not(ancestor::script or ancestor::style or ancestor::svg)]")).split())


def _same_publisher(url: str, domain: str) -> bool:
    try:
        parts = urlsplit(url)
        hostname = (parts.hostname or "").lower()
        return (parts.scheme in {"http", "https"} and not parts.username and not parts.password
                and (hostname == domain or hostname.endswith("." + domain)))
    except ValueError:
        return False


def _article_url(raw: str, base: str, domain: str) -> str:
    url = urljoin(base, raw)
    if not _same_publisher(url, domain):
        return ""
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if len(parts) < 2 or any(NON_ARTICLE.fullmatch(part) for part in parts) or ASSET.search(parts[-1]):
        return ""
    if len(re.findall(r"[^\W_]+", parts[-1])) < 4 and not set(parts[:-1]) & {"article", "articles", "node"}:
        return ""
    try:
        return clean_url(url)
    except ValueError:
        return ""


def _headline(anchor) -> str:
    headings = anchor.xpath(".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5]")
    return _text(min(headings, key=lambda h: int(h.tag[1]))) if headings else " ".join(
        (anchor.get("title") or anchor.get("aria-label") or _text(anchor)).split()
    )


def _navigation(anchor) -> bool:
    return any(parent.tag in {"nav", "header", "footer"} or parent.get("role") == "navigation"
               or re.search(r"(?:^|[\s_-])(?:menu|navbar|navigation)(?:$|[\s_-])", parent.get("class", ""), re.I)
               for parent in anchor.iterancestors())


def _card(anchor, base: str, url: str, domain: str):
    chosen = anchor
    for parent in anchor.iterancestors():
        if parent.tag in {"body", "html", "main", "section", "nav", "header", "footer"}:
            break
        other_stories = {
            _article_url(a.get("href", ""), base, domain) for a in parent.xpath(".//a[@href]")
        } - {"", url}
        if other_stories:
            break
        chosen = parent
        if parent.tag in {"article", "li"}:
            break
    return chosen


def _parse_date(raw: str, now: datetime) -> tuple[datetime | None, str]:
    raw = " ".join(raw.split())
    match = RELATIVE_DATE.fullmatch(raw)
    if match:
        seconds = int(match[1]) * {"m": 60, "h": 3600, "d": 86400}[match[2].lower()[0]]
        return now - timedelta(seconds=seconds), "relative"
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return value.replace(tzinfo=UTC), "day"
        if value.tzinfo:
            return value.astimezone(UTC), "timestamp"
    except ValueError:
        pass
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC), "day"
        except ValueError:
            pass
    return None, "unknown"


def _publication_date(card, url: str, source: Source, now: datetime):
    values = card.xpath('.//time[not(@itemprop="dateModified")]/@datetime|.//*[@itemprop="datePublished"]/@content')
    for node in card.xpath('.//time[not(@itemprop="dateModified")]|.//*[@class]|.//span'):
        if node.tag == "time" or RELATIVE_DATE.fullmatch(_text(node)) or re.search(r"(?:time|date|published|ago)", node.get("class", ""), re.I):
            if re.search(r"updated|modified", node.get("class", ""), re.I):
                continue
            text = _text(node)
            match = RELATIVE_DATE.search(text) or VISIBLE_DATE.search(text)
            if match:
                values.append(match[0])
    for raw in values:
        value, precision = _parse_date(raw, now)
        if value is not None:
            return value, precision, "listing_card", raw
    # Benchmark accepted National literal dated paths as apparent day-level news
    # dates. Keep that weaker provenance explicit; no midnight precision claim.
    if source.name == "The National":
        match = re.search(r"/(\d{4}/\d{2}/\d{2})/", url)
        if match:
            raw = match[1].replace("/", "-")
            value, precision = _parse_date(raw, now)
            return value, precision, "literal_url_path; apparent publication day only", raw
    return None, "unknown", "unknown", ""


def extract_recent_articles(markup: bytes, source: Source, *, now: datetime, freshness_days: int, stats: dict) -> list[Article]:
    """Extract metadata only, bounded by candidate anchors and accepted articles."""
    domain = TARGET_PUBLISHERS[source.name]
    tree = html.fromstring(markup.decode("utf8", errors="replace"))
    accepted, discovered, accepted_urls = [], set(), set()
    for anchor in tree.xpath("//a[@href]"):
        if stats["candidate_anchors_considered"] >= MAX_CANDIDATE_ANCHORS or len(accepted) >= MAX_RECENT_ARTICLES:
            break
        if _navigation(anchor):
            continue
        url = _article_url(anchor.get("href"), source.source_url, domain)
        title = _headline(anchor)
        if not url or len(title) < 20 or len(title.split()) < 4:
            continue
        stats["candidate_anchors_considered"] += 1
        if url in discovered:
            stats["duplicate_anchor_links"] += 1
        discovered.add(url)
        if url in accepted_urls:
            continue
        context = _card(anchor, source.source_url, url, domain)
        published, precision, provenance, raw = _publication_date(context, url, source, now)
        if published is None:
            stats["undated_anchor_rejections"] += 1
            continue
        if not now - timedelta(days=freshness_days) <= published <= now:
            stats["stale_or_future_anchor_rejections"] += 1
            continue
        snippets = [_text(p) for p in context.xpath(".//p[not(.//a)]")
                    if not re.search(r"headline", p.get("class", ""), re.I)]
        snippet = next((p for p in snippets if len(p) >= 40 and p != title), "")
        article = Article(
            title=title, url=url, canonical_url=url, source_name=source.name,
            source_page_id=source.notion_page_id, published_date=published, collected_date=now,
            snippet=snippet[:600], region=list(source.region), topic_focus=list(source.topic_focus),
            source_editorial_quality=source.editorial_quality,
            publisher_key=source.notion_page_id or domain, url_resolution_status="publisher_url",
            discovery_method="direct_site", discovery_page=source.source_url,
            date_provenance=provenance, date_precision=precision,
        )
        article.discovery_origins = [_origin(article, date_raw=raw)]
        accepted.append(article)
        accepted_urls.add(url)
    stats["direct_candidates_discovered"] = len(discovered)
    stats["recent_direct_candidates_accepted"] = len(accepted)
    stats["limit_reached"] = stats["candidate_anchors_considered"] == MAX_CANDIDATE_ANCHORS or len(accepted) == MAX_RECENT_ARTICLES
    return accepted


def _origin(article: Article, **extra) -> dict:
    return dict(discovery_method=acquisition_method(article), url=article.url,
                canonical_url=article.canonical_url, title=article.title,
                published_date=article.published_date.isoformat() if article.published_date else None,
                snippet=article.snippet, discovery_page=article.discovery_page,
                date_provenance=article.date_provenance, date_precision=article.date_precision, **extra)


def _headline_key(article: Article) -> str:
    # Reuse actual publisher-suffix stripping from the existing event code, but
    # require FULL normalized-headline equality, not its broader fuzzy threshold.
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", _event_title(article)).casefold()))


def _clear_match(feed: Article, direct: Article) -> bool:
    if feed.source_page_id != direct.source_page_id or feed.source_name != direct.source_name:
        return False
    try:
        canonical = clean_url(feed.canonical_url or feed.url)
    except ValueError:
        return False  # preserve invalid feed input for normal objective cleanup
    if canonical == direct.canonical_url:
        return True
    key = _headline_key(feed)
    if len(key.split()) < 4 or key != _headline_key(direct) or not isinstance(feed.published_date, datetime):
        return False
    published = feed.published_date.replace(tzinfo=UTC) if feed.published_date.tzinfo is None else feed.published_date
    return abs((published - direct.published_date).total_seconds()) <= 86400


def merge_supplement(feed: list[Article], direct: list[Article], stats: dict[str, dict]) -> list[Article]:
    """Never remove a feed-only story. Ambiguous many-to-one matches stay apart."""
    merged = list(feed)
    # Resolve the bipartite matches before mutating representatives. This avoids
    # order-dependent URL choice when two direct pages share a headline.
    matches = [[i for i, article in enumerate(feed) if _clear_match(article, extra)] for extra in direct]
    uses = Counter(i for positions in matches for i in positions)
    for extra, positions in zip(direct, matches):
        counts = stats[extra.source_name]
        if len(positions) != 1 or uses[positions[0]] != 1:
            merged.append(extra)
            if positions:
                counts["ambiguous_matches_retained"] += 1
            else:
                counts["direct_only_candidates"] += 1
            continue
        position = positions[0]
        original = feed[position]
        counts["direct_feed_headline_matches"] += 1
        counts["duplicates_removed"] += 1
        wrapper = is_google_news_url(original.canonical_url or original.url)
        # Native/direct feed canonicals are already useful: retain them verbatim.
        prefer_direct = wrapper
        representative = extra if prefer_direct else original
        date_source = representative if representative.published_date else extra
        origins = [*(original.discovery_origins or [_origin(original)]), *(extra.discovery_origins or [_origin(extra)])]
        merged[position] = replace(
            original, canonical_url=representative.canonical_url,
            published_date=date_source.published_date,
            snippet=extra.snippet or original.snippet,
            discovery_method="direct_site" if prefer_direct else acquisition_method(original),
            discovery_page=representative.discovery_page,
            date_provenance=date_source.date_provenance, date_precision=date_source.date_precision,
            url_resolution_status="resolved_direct_site" if wrapper else original.url_resolution_status,
            feed_wrapper_replaced=wrapper, discovery_origins=origins,
            url_hash="", content_hash="",  # existing preparation refreshes identity
        )
        counts["wrappers_replaced_by_direct_urls"] += int(wrapper)
    return merged


def _source_stats(name: str, feed: list[Article]) -> dict:
    return dict(status="not_due_or_inactive", listing_requests=0, candidate_anchors_considered=0,
                direct_candidates_discovered=0, recent_direct_candidates_accepted=0,
                feed_candidates_collected=sum(a.source_name == name for a in feed),
                direct_feed_headline_matches=0, wrappers_replaced_by_direct_urls=0,
                direct_only_candidates=0, ambiguous_matches_retained=0, duplicates_removed=0,
                duplicate_anchor_links=0, undated_anchor_rejections=0, stale_or_future_anchor_rejections=0)


def supplement_articles(feed: list[Article], sources: list[Source], *, now: datetime,
                        freshness_days: int = 7, client: httpx.Client | None = None) -> HybridDiscoveryResult:
    stats = {name: _source_stats(name, feed) for name in TARGET_PUBLISHERS}
    direct, contacted = [], set()
    now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    owned = client is None
    client = client if client is not None else httpx.Client(
        trust_env=False, follow_redirects=False,
        timeout=httpx.Timeout(connect=5, read=20, write=10, pool=5),
    )
    try:
        for source in sources:
            if source.name not in TARGET_PUBLISHERS or source.source_type != "Publisher" or source.name in contacted:
                continue
            contacted.add(source.name)
            counts = stats[source.name]
            started = perf_counter()
            if not _same_publisher(source.source_url, TARGET_PUBLISHERS[source.name]):
                counts["status"] = "invalid_source_url"
                continue
            try:
                counts["listing_requests"] = 1
                with client.stream("GET", source.source_url, headers=HEADERS, follow_redirects=False) as response:
                    counts["http_status"] = response.status_code
                    if 300 <= response.status_code < 400:
                        counts["status"] = "redirect_skipped_one_request_limit"
                        continue
                    response.raise_for_status()
                    if "html" not in response.headers.get("content-type", "text/html").lower():
                        counts["status"] = "unsupported_content"
                        continue
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ValueError("listing exceeds byte ceiling")
                        body.extend(chunk)
                direct.extend(extract_recent_articles(bytes(body), source, now=now, freshness_days=freshness_days, stats=counts))
                counts["status"] = "success"
            except Exception as exc:  # optional source failure cannot abort feeds
                # Category only: no provider response/request details in audit.
                counts.update(status="failed", error_type=type(exc).__name__)
            finally:
                counts["duration_ms"] = round((perf_counter() - started) * 1000)
    finally:
        if owned:
            client.close()
    return HybridDiscoveryResult(merge_supplement(feed, direct, stats), stats)

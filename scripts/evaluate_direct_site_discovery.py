"""Opt-in, read-only discovery benchmark; never imported by production ingestion.

Run listing fetches with the existing isolated Scrapling interpreter, and feed /
ArticleRetriever work with the project interpreter. No dependency installation,
Notion writes, model calls, browser automation, or ingestion-state access.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from lxml import etree
from lxml import html as lhtml
import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.preview/evaluations/direct_site_discovery_20261019'
MAX_BYTES = 2_000_000
MAX_CONSIDERED = 100
MAX_ACCEPTED = 50
MAX_ARTICLE_REQUESTS = 36
EXCLUDED = {'Reuters', 'S&P Global'}
REFUSED = {401, 402, 403, 407, 429, 451}
HEADERS = {'User-Agent': 'SOMA-MATER-Research/1.0', 'Accept': 'text/html,application/xhtml+xml'}
NON_ARTICLE = re.compile(
    r'^(?:about(?:-us)?|contact(?:-us)?|login|log-in|sign-?in|sign-?up|register|registration|'
    r'newsletter[s]?|subscribe|subscription[s]?|search|tag[s]?|author[s]?|profile[s]?|'
    r'category|categories|topic[s]?|privacy|terms|advertis(?:e|ing)|cookie[s]?|'
    r'account|careers|jobs?|collections?|events?|podcasts?|videos?|photos?|pictures?|cartoons?|gallery|galleries|'
    r'help|faq|sitemap|rss|feed|feeds)(?:\b|[-_])', re.I)
ASSET = re.compile(r'\.(?:jpg|jpeg|png|gif|svg|webp|ico|css|js|pdf|zip|xml|mp4|mp3|woff2?)$', re.I)
MONTHS = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE_PATTERN = re.compile(r'\b(?:\d{4}-\d{2}-\d{2}(?:T[\d:.+Z-]+)?|\d{1,2}\s+' + MONTHS + r'\s+\d{4}|' + MONTHS + r'\s+\d{1,2},?\s+\d{4}|\d+\s*(?:minutes?|mins?|hours?|hrs?|days?|[mhd])\s+ago|today|yesterday)\b', re.I)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def compact(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def host(url):
    return (urlsplit(url).hostname or '').lower().removeprefix('www.')


def public(url):
    try:
        p = urlsplit(url)
        if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
            return False
        if p.hostname == 'localhost' or '.' not in p.hostname:
            return False
        try:
            return ipaddress.ip_address(p.hostname).is_global
        except ValueError:
            return True
    except ValueError:
        return False


def same_publisher(url, source_url):
    return public(url) and (host(url) == host(source_url) or host(url).endswith('.' + host(source_url)))


def clean_link(url):
    p = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid', 'ref', 'source'}])
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/') or '/', query, ''))


def slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def sources(out=OUT):
    return read(out / 'sources.json')['sources']


def snapshot(out=OUT):
    """Read only Source Registry configuration, never article/health writes."""
    from research_automation.config import load_settings
    from research_automation.clients.notion_client import NotionClient
    from research_automation.pipeline.source_registry import load_active_sources
    if (out / 'sources.json').exists():
        raise SystemExit('sources.json already exists; use a new output directory for another snapshot')
    paths = [p for p in ROOT.iterdir() if p.is_file()]
    for folder in ('src', 'scripts', 'tests', 'docs', '.local_state'):
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    write(out / 'protected_before.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    settings = load_settings()
    rows = load_active_sources(NotionClient(settings.notion_token), settings)
    write(out / 'sources.json', {'captured_at': datetime.now(timezone.utc).isoformat(), 'sources': [
        dict(name=s.name, source_url=s.source_url, feed_url=s.feed_url,
             collection_method=s.collection_method, source_type=s.source_type)
        for s in rows if s.source_type == 'Publisher']})


def static_fetch(source, out=OUT, get=None):
    """A transparent bounded static request, with same-publisher redirects only."""
    if source['name'] in EXCLUDED:
        result = {'publisher': source['name'], 'status': 'excluded_prior_refusal', 'requests': 0}
        write(out / 'listing_fetches' / (slug(source['name']) + '.json'), result)
        return result
    if get is None:
        from scrapling.fetchers import Fetcher
        get = Fetcher.get
    url = source['source_url']
    started = time.perf_counter()
    result = {'publisher': source['name'], 'source_url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(), 'requests': 0, 'redirects': []}
    too_large = False
    try:
        for _ in range(6):
            if not same_publisher(url, source['source_url']):
                result['status'] = 'unsafe_or_external_redirect'
                break
            chunks, size, too_large = [], 0, False

            def receive(chunk):
                nonlocal size, too_large
                size += len(chunk)
                if size > MAX_BYTES:
                    too_large = True
                    return 0
                chunks.append(chunk)
                return len(chunk)

            result['requests'] += 1
            response = get(url, impersonate=None, stealthy_headers=False, headers=HEADERS,
                           retries=1, timeout=20, follow_redirects=False, max_redirects=0,
                           content_callback=receive)
            status = response.status
            result.update(http_status=status, final_url=url)
            if too_large:
                result['status'] = 'too_large'
                break
            if status in REFUSED:
                result['status'] = 'blocked'
                break
            if status in {301, 302, 303, 307, 308}:
                destination = urljoin(url, response.headers.get('location', response.headers.get('Location', '')))
                result['redirects'].append(destination)
                url = destination
                continue
            if status != 200:
                result['status'] = 'fetch_failed'
                break
            markup = b''.join(chunks)
            content_type = str(response.headers.get('content-type', response.headers.get('Content-Type', '')))
            if content_type and 'html' not in content_type:
                result['status'] = 'unsupported_content'
                break
            path = out / 'pages' / (slug(source['name']) + '.html')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(markup)
            result.update(status='fetched', bytes=len(markup), html_file=str(path.relative_to(out)), sha256=hashlib.sha256(markup).hexdigest())
            break
        else:
            result['status'] = 'redirect_limit'
    except Exception as exc:
        result.update(status='too_large' if too_large else 'fetch_failed', error=type(exc).__name__ + ': ' + str(exc)[:250])
    result['latency_seconds'] = round(time.perf_counter() - started, 3)
    write(out / 'listing_fetches' / (slug(source['name']) + '.json'), result)
    return result


def fetch_listings(out=OUT):
    if any((out / 'listing_fetches').glob('*.json')):
        raise SystemExit('listing snapshot already exists; use a new output directory to repeat live fetching')
    # No inherited proxy settings; no browser impersonation or stealth headers.
    import os
    for key in list(os.environ):
        if key.lower() in {'http_proxy', 'https_proxy', 'all_proxy'}:
            os.environ.pop(key, None)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda s: static_fetch(s, out), sources(out)):
            print(json.dumps(result), flush=True)


def parse_date(raw, now):
    """Parse supplied publication metadata only; never dates from body prose."""
    raw = compact(raw)
    if not raw:
        return None, 'unknown'
    try:
        if re.fullmatch(r'\d{10}|\d{13}', raw):
            stamp = int(raw) / (1000 if len(raw) == 13 else 1)
            return datetime.fromtimestamp(stamp, timezone.utc), 'timestamp'
        relative = re.fullmatch(r'(\d+)\s*(minutes?|mins?|hours?|hrs?|days?|[mhd])\s+ago', raw, re.I)
        if relative:
            quantity, unit = int(relative[1]), relative[2].lower()[0]
            return now - timedelta(seconds=quantity * {'m': 60, 'h': 3600, 'd': 86400}[unit]), 'relative'
        if raw.lower() in {'today', 'yesterday'}:
            return (now - timedelta(days=int(raw.lower() == 'yesterday'))).replace(hour=0, minute=0, second=0, microsecond=0), 'date_only'
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc), 'date_only'
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc), 'timestamp'
        # An unzoned time is not silently assumed to be UTC.
        return None, 'timezone_unknown'
    except (ValueError, OverflowError, OSError):
        pass
    for fmt in ('%d %B %Y', '%d %b %Y', '%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%b %d %Y'):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc), 'date_only'
        except ValueError:
            pass
    try:
        value = parsedate_to_datetime(raw)
        if value.tzinfo:
            return value.astimezone(timezone.utc), 'timestamp'
    except (ValueError, TypeError):
        pass
    return None, 'unknown'


def freshness(raw, now):
    value, precision = parse_date(raw, now)
    if value is None:
        return {'published_at': None, 'date_precision': precision, 'freshness': 'unknown'}
    if precision == 'date_only':
        # Interval overlap, rather than pretending midnight is an exact time.
        if value.date() > now.date():
            state = 'future'
        elif now.date() - timedelta(days=2) <= value.date():
            state = 'recent_date_only'
        else:
            state = 'boundary_date_only' if value.date() == (now - timedelta(days=3)).date() else 'older'
    else:
        state = 'recent' if now - timedelta(days=3) <= value <= now else ('future' if value > now else 'older')
    return {'published_at': value.isoformat(), 'date_precision': precision, 'freshness': state}


def normalized_title(title, publisher=''):
    title = re.sub(r'\s+[-|–—]\s*' + re.escape(publisher) + r'\s*$', '', title, flags=re.I) if publisher else title
    return ' '.join(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', title).casefold()))


def structured_documents(tree):
    """Read JSON data, never execute JavaScript. No network or API guessing."""
    decoder = json.JSONDecoder()
    for node in tree.xpath('//script'):
        text = (node.text or '').strip()
        if text.startswith(('{', '[')):
            try:
                yield json.loads(text)
            except ValueError:
                pass
        # Benchmark exception: Arc exposes JSON objects in Fusion assignments.
        # Parsing these assignments does not execute the surrounding script.
        if node.get('id') == 'fusion-metadata':
            for match in re.finditer(r'Fusion\.(?:globalContent|contentCache)\s*=\s*', text):
                try:
                    yield decoder.raw_decode(text[match.end():])[0]
                except ValueError:
                    pass


def walk_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_objects(child)


def structured_index(tree, base):
    index = {}
    date_keys = ('datePublished', 'first-published-at', 'first_publish_date', 'published_at', 'publish_date', 'published-at', 'publishedAt')
    for document in structured_documents(tree):
        for obj in walk_objects(document):
            date = next((obj[k] for k in date_keys if obj.get(k) is not None), None)
            # Do not use WebPage/site-level publication or modification dates.
            kind = obj.get('@type', '')
            if isinstance(kind, list):
                kind = ' '.join(kind)
            if date is None or kind in {'WebPage', 'WebSite', 'Organization', 'NewsMediaOrganization'}:
                continue
            url = next((obj[k] for k in ('url', 'website_url', 'canonical_url', 'slug', '@id') if isinstance(obj.get(k), str)), '')
            if not url:
                continue
            url = clean_link(urljoin(base, url))
            index[url] = {'date_raw': str(date), 'date_source': 'embedded_article_json',
                          'snippet': compact(obj.get('description') or obj.get('subheadline') or obj.get('subtitle'))[:600],
                          'section': compact(obj.get('articleSection'))}
    return index


def visible_text(node):
    return compact(' '.join(node.xpath('.//text()[not(ancestor::script or ancestor::style or ancestor::svg)]')))


def anchor_title(anchor):
    heads = anchor.xpath('.//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5]')
    if heads:
        return visible_text(min(heads, key=lambda h: int(h.tag[1])))
    return compact(anchor.get('title') or anchor.get('aria-label') or visible_text(anchor))


def is_navigation(anchor):
    return any(p.tag in {'nav', 'header', 'footer'} or p.get('role') == 'navigation' or re.search(r'(?:^|[\s_-])(?:menu|navbar|navigation)(?:$|[\s_-])', p.get('class', ''), re.I) for p in anchor.iterancestors())


def article_path(url):
    parts = [p for p in urlsplit(url).path.split('/') if p]
    if not parts or ASSET.search(parts[-1]) or any(NON_ARTICLE.match(p) for p in parts):
        return False
    # URL shape + a headline is enough for the bounded discovery experiment;
    # no relevance keywords or headline-specific rules are used.
    words = re.findall(r'[^\W_]+', parts[-1])
    return len(parts) >= 2 and (len(words) >= 4 or any(p.lower() in {'article', 'articles', 'node', 'story', 'stories'} for p in parts[:-1]))


def card_context(anchor, base, article_url):
    """Stop before a container contains a second distinct story."""
    chosen = anchor
    for parent in anchor.iterancestors():
        if parent.tag in {'body', 'html', 'main', 'section', 'nav', 'header', 'footer'}:
            break
        others = {clean_link(urljoin(base, a.get('href', ''))) for a in parent.xpath('.//a[@href]') if article_path(urljoin(base, a.get('href', ''))) and len(anchor_title(a)) >= 20}
        if others - {article_url}:
            break
        chosen = parent
        if parent.tag in {'article', 'li'}:
            break
    return chosen


def card_metadata(card, title):
    dates = card.xpath('.//time/@datetime|.//time/text()|.//*[@itemprop="datePublished"]/@content|.//@date-utc')
    # date-utc is a documented benchmark-only ZAWYA markup exception.
    for node in card.xpath('.//*[@class]'):
        if re.search(r'(?:^|[\s_-])(?:time|date|published|timestamp|ago)(?:$|[\s_-])', node.get('class', ''), re.I):
            value = visible_text(node)
            match = DATE_PATTERN.search(value)
            if match:
                dates.append(match[0])
    if not dates:
        # A tightly bounded single-story card may expose e.g. "9m ago".
        match = re.search(r'(?<!\w)\d+\s*(?:minutes?|mins?|hours?|hrs?|days?|[mhd])\s+ago\b', visible_text(card), re.I)
        if match:
            dates.append(match[0])
    paragraphs = [visible_text(p) for p in card.xpath('.//p') if not p.xpath('.//a') and not re.search(r'headline', p.get('class', ''), re.I)]
    snippets = [p for p in paragraphs if len(p) >= 40 and normalized_title(p) != normalized_title(title)]
    sections = card.xpath('.//*[@class and (contains(@class,"category") or contains(@class,"keyword") or contains(@class,"section"))]')
    section = next((visible_text(s) for s in sections if 2 <= len(visible_text(s)) < 60), '')
    return {'date_raw': compact(dates[0]) if dates else '', 'date_source': 'listing_card' if dates else 'unknown', 'snippet': snippets[0][:600] if snippets else '', 'section': section}


def extract_candidates(markup, source, fetched_at, discovery_page=None):
    started = time.perf_counter()
    now = datetime.fromisoformat(fetched_at)
    base = discovery_page or source['source_url']
    tree = lhtml.fromstring(markup.decode('utf8', errors='replace') if isinstance(markup, bytes) else markup)
    index = structured_index(tree, base)
    rejects, accepted, seen = Counter(), [], set()
    considered, duplicates = 0, 0
    anchors = tree.xpath('//a[@href]')
    for anchor in anchors:
        url = clean_link(urljoin(base, anchor.get('href')))
        title = anchor_title(anchor)
        if not same_publisher(url, source['source_url']):
            rejects['external_or_unsafe'] += 1
            continue
        if is_navigation(anchor):
            rejects['navigation'] += 1
            continue
        if not article_path(url):
            rejects['non_article_path'] += 1
            continue
        if len(title) < 20 or len(title.split()) < 4:
            rejects['no_usable_headline'] += 1
            continue
        if considered >= MAX_CONSIDERED or len(accepted) >= MAX_ACCEPTED:
            break
        considered += 1
        if url in seen:
            duplicates += 1
            continue
        seen.add(url)
        card = card_context(anchor, base, url)
        metadata = card_metadata(card, title)
        if url in index:
            structured = index[url]
            metadata.update({k: v for k, v in structured.items() if v})
        # Only literal dated URL paths, never image paths or headline years.
        if not metadata['date_raw']:
            match = re.search(r'/(\d{4})/(\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/(\d{2})/', url, re.I)
            if match:
                try:
                    value = datetime.strptime('/'.join(match.groups()), '%Y/%m/%d' if match[2].isdigit() else '%Y/%b/%d')
                    metadata.update(date_raw=value.strftime('%Y-%m-%d'), date_source='literal_url_date')
                except ValueError:
                    pass
        accepted.append(dict(publisher=source['name'], title=title[:500], url=url, discovery_page=base,
                             **metadata, **freshness(metadata['date_raw'], now)))
    return dict(publisher=source['name'], fetched_at=fetched_at, total_anchors=len(anchors), considered=considered,
                accepted=accepted, duplicate_links=duplicates, rejected=dict(rejects),
                cap_reached=considered >= MAX_CONSIDERED or len(accepted) >= MAX_ACCEPTED,
                structured_article_records=len(index), parse_latency_seconds=round(time.perf_counter()-started, 4))


def analyze(out=OUT):
    for source in sources(out):
        path = out / 'listing_fetches' / (slug(source['name']) + '.json')
        fetch = read(path) if path.exists() else {'status': 'excluded_prior_refusal'}
        if fetch['status'] != 'fetched':
            result = {'publisher': source['name'], 'fetch': fetch, 'accepted': []}
        else:
            result = extract_candidates((out / fetch['html_file']).read_bytes(), source, fetch['fetched_at'], fetch['final_url'])
            result['fetch'] = fetch
        write(out / 'direct' / (slug(source['name']) + '.json'), result)
        print(source['name'], len(result['accepted']), Counter(x['freshness'] for x in result['accepted']), flush=True)


def feed_items(raw, source, fetched_at):
    import calendar
    import feedparser
    tree = feedparser.parse(raw)
    now = datetime.fromisoformat(fetched_at)
    entries, seen, duplicates = [], set(), 0
    for entry in tree.entries:
        url = clean_link(entry.get('link', ''))
        title = compact(entry.get('title'))
        if not public(url) or not title:
            continue
        if url in seen:
            duplicates += 1
            continue
        seen.add(url)
        description = entry.get('summary', '')
        try:
            node = lhtml.fragment_fromstring(description, create_parent='div')
            # Google News descriptions commonly repeat title + publisher only.
            for anchor in node.xpath('.//a'):
                if normalized_title(visible_text(anchor), source['name']) == normalized_title(title, source['name']):
                    anchor.drop_tree()
            snippet = visible_text(node)
        except (ValueError, TypeError):
            snippet = ''
        if len(snippet) < 40 or normalized_title(snippet, source['name']) == normalized_title(title, source['name']):
            snippet = ''
        stamp = entry.get('published_parsed')
        date_raw = datetime.fromtimestamp(calendar.timegm(stamp), timezone.utc).isoformat() if stamp else ''
        entries.append(dict(publisher=source['name'], title=title, url=url, discovery_page=source['feed_url'],
                            date_raw=date_raw, date_source='rss_published' if stamp else 'unknown',
                            snippet=snippet[:600], section=compact((entry.get('tags') or [{}])[0].get('term')),
                            wrapper=host(url) == 'news.google.com', direct_publisher=same_publisher(url, source['source_url']),
                            **freshness(date_raw, now)))
    return {'publisher': source['name'], 'entries': entries, 'duplicate_links': duplicates,
            'raw_entries': len(tree.entries), 'parse_warning': bool(tree.bozo)}


def fetch_feed(source, out=OUT):
    import httpx
    fetched_at = datetime.now(timezone.utc).isoformat()
    result = {'publisher': source['name'], 'feed_url': source['feed_url'], 'fetched_at': fetched_at, 'entries': []}
    started = time.perf_counter()
    try:
        headers = dict(HEADERS, Accept='application/rss+xml,application/xml,text/xml')
        with httpx.Client(timeout=20, trust_env=False, follow_redirects=True, max_redirects=5) as client:
            with client.stream('GET', source['feed_url'], headers=headers) as response:
                result['http_status'] = response.status_code
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise ValueError('feed exceeds byte ceiling')
        path = out / 'feeds' / (slug(source['name']) + '.xml')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        result.update(feed_items(bytes(body), source, fetched_at), status='fetched', bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    except Exception as exc:
        result.update(status='fetch_failed', error=type(exc).__name__ + ': ' + str(exc)[:200])
    result['latency_seconds'] = round(time.perf_counter() - started, 3)
    write(out / 'feeds' / (slug(source['name']) + '.json'), result)
    return result


def fetch_feeds(out=OUT):
    if any((out / 'feeds').glob('*.json')):
        raise SystemExit('feed snapshot already exists; use a new output directory to repeat live fetching')
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda s: fetch_feed(s, out), [s for s in sources(out) if s['name'] not in EXCLUDED]):
            print(result['publisher'], result['status'], len(result['entries']), Counter(x['freshness'] for x in result['entries']), flush=True)


def stats(items):
    recent = [i for i in items if i['freshness'] in {'recent', 'recent_date_only'}]
    return dict(total=len(items), recent=len(recent), recent_exact=sum(i['freshness'] == 'recent' for i in items),
                boundary_uncertain=sum(i['freshness'] == 'boundary_date_only' for i in items),
                dates=sum(i['published_at'] is not None for i in items), titles=sum(len(i['title']) >= 20 for i in items),
                snippets=sum(len(i['snippet']) >= 40 for i in items),
                wrappers=sum(host(i['url']) == 'news.google.com' for i in items),
                direct=sum(i.get('direct_publisher', host(i['url']) != 'news.google.com') for i in items),
                date_sources=dict(Counter(i['date_source'] for i in items)))


def compare(source, direct, feed):
    a = {normalized_title(i['title'], source['name']) for i in direct if i['freshness'] in {'recent', 'recent_date_only'}}
    b = {normalized_title(i['title'], source['name']) for i in feed if i['freshness'] in {'recent', 'recent_date_only'}}
    all_a = {normalized_title(i['title'], source['name']) for i in direct}
    all_b = {normalized_title(i['title'], source['name']) for i in feed}
    undated_a = {normalized_title(i['title'], source['name']) for i in direct if i['freshness'] == 'unknown'}
    return dict(direct=stats(direct), feed=stats(feed), overlap=len(a & b), unique_direct=len(a-b), unique_feed=len(b-a),
                overlap_all_dates=len(all_a & all_b), recent_feed_matches_undated_direct=len(b & undated_a),
                match_method='NFKC/case/punctuation normalization, exact equality; publisher suffix removed',
                overlap_titles=sorted(a & b))


def comparison(out=OUT):
    rows = []
    for source in sources(out):
        direct = read(out / 'direct' / (slug(source['name']) + '.json'))
        path = out / 'feeds' / (slug(source['name']) + '.json')
        feed = read(path) if path.exists() else {'entries': [], 'status': 'not_tested'}
        row = dict(publisher=source['name'], collection_method=source['collection_method'],
                   direct_fetch_status=direct['fetch']['status'], feed_fetch_status=feed['status'],
                   direct_latency_seconds=round(direct['fetch'].get('latency_seconds', 0) + direct.get('parse_latency_seconds', 0), 3) if direct['fetch'].get('latency_seconds') is not None else None,
                   listing_fetch_latency_seconds=direct['fetch'].get('latency_seconds'), parse_latency_seconds=direct.get('parse_latency_seconds'),
                   feed_latency_seconds=feed.get('latency_seconds'),
                   considered=direct.get('considered', 0), direct_duplicate_links=direct.get('duplicate_links', 0),
                   feed_duplicate_links=feed.get('duplicate_links', 0), rejected=direct.get('rejected', {}),
                   **compare(source, direct['accepted'], feed['entries']))
        rows.append(row)
        print(source['name'], 'direct', row['direct']['recent'], 'feed', row['feed']['recent'], 'overlap', row['overlap'])
    write(out / 'comparison.json', rows)


class RequestLedger:
    def __init__(self, limit=MAX_ARTICLE_REQUESTS):
        if not 0 <= limit <= MAX_ARTICLE_REQUESTS:
            raise ValueError('article request budget must be at most 36')
        self.limit, self.requests = limit, []


class BudgetTransport(httpx.BaseTransport):
    """Count actual sends, including redirects. No retry or alternate fetcher."""
    def __init__(self, ledger, source_url, transport=None):
        self.ledger, self.source_url = ledger, source_url
        self.transport = transport if transport is not None else httpx.HTTPTransport(retries=0)
        self.body, self.final_url, self.status, self.guard_reason = bytearray(), '', None, ''

    def handle_request(self, request):
        url = str(request.url)
        if len(self.ledger.requests) >= self.ledger.limit:
            self.guard_reason = 'request_budget_exhausted'
        elif not same_publisher(url, self.source_url) and host(url) != 'news.google.com':
            self.guard_reason = 'external_redirect_refused'
        if self.guard_reason:
            raise httpx.RequestError(self.guard_reason, request=request)
        self.ledger.requests.append({'url': url, 'started_at': datetime.now(timezone.utc).isoformat()})
        self.body.clear()
        self.final_url = url
        response = self.transport.handle_request(request)
        self.status = response.status_code
        self.ledger.requests[-1]['http_status'] = self.status
        return response

    def close(self):
        self.transport.close()


class ObservedClient(httpx.Client):
    @contextmanager
    def stream(self, *args, **kwargs):
        with super().stream(*args, **kwargs) as response:
            original = response.iter_bytes

            def observed(*args, **kwargs):
                for chunk in original(*args, **kwargs):
                    remaining = MAX_BYTES - len(self._transport.body)
                    if remaining > 0:
                        self._transport.body.extend(chunk[:remaining])
                    yield chunk
            response.iter_bytes = observed
            yield response


def retrieve_one(item, source, ledger, transport=None, out=None):
    """Call the unchanged production retriever; audit its output separately."""
    from research_automation.models.article import Article
    from research_automation.pipeline.article_retrieval import ArticleRetriever
    capture = BudgetTransport(ledger, source['source_url'], transport)
    before, started = len(ledger.requests), time.perf_counter()
    article = Article(item['title'], item['url'], item['url'], source['name'], '')
    with ObservedClient(transport=capture, trust_env=False, follow_redirects=True, max_redirects=5,
                        timeout=httpx.Timeout(connect=5, read=15, write=10, pool=5)) as client:
        result = ArticleRetriever(client=client).retrieve(article)
    markup = capture.body.decode('utf8', errors='replace')
    page_title, paragraphs, matched = '', 0, 0
    challenge = False
    try:
        tree = lhtml.fromstring(markup)
        page_title = compact(' '.join(tree.xpath('//h1//text()|//title/text()|//meta[@property="og:title"]/@content')))
        paragraphs = sum(len(visible_text(p)) >= 60 for p in tree.xpath('//p'))
        expected = set(normalized_title(item['title']).split())
        actual = set(normalized_title(page_title).split())
        matched = len(expected & actual) / max(1, len(expected))
        challenge = bool(re.search(r'access denied|just a moment|verify.{0,15}human|captcha|page not found', page_title, re.I) or re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', markup, re.I))
    except (ValueError, TypeError, etree.LxmlError):
        pass
    audited = result.evidence_retrieval_status
    if challenge:
        audited = 'blocked_or_paywalled'
    elif audited == 'extracted' and (matched < .45 or paragraphs < 2 or host(capture.final_url) == 'news.google.com'):
        audited = 'article_body_not_verified'
    row = dict(publisher=source['name'], title=item['title'], url=item['url'], freshness=item['freshness'],
               raw_status=result.evidence_retrieval_status, audited_status=audited,
               canonical_url=result.canonical_url, url_resolution_status=result.url_resolution_status,
               final_url=capture.final_url, http_status=capture.status, guard_reason=capture.guard_reason,
               characters=len(result.article_text), text_sha256=hashlib.sha256(result.article_text.encode()).hexdigest(),
               page_title=page_title[:500], headline_token_overlap=round(matched, 3), substantial_paragraphs=paragraphs,
               requests=len(ledger.requests)-before, latency_seconds=round(time.perf_counter()-started, 3))
    if out is not None and markup:
        path = out / 'retrieval_pages' / (hashlib.sha256(item['url'].encode()).hexdigest()[:16] + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(capture.body)
        row['html_file'] = str(path.relative_to(out))
    return row


def retrieval_sample(source, direct, feed):
    """Two direct examples per source, first matching the feed where possible.

    A third request targets that exact story's configured Google wrapper. No
    wrapper guessed from a title and no Google URL decoding service.
    """
    feed_by_title = {normalized_title(x['title'], source['name']): x for x in feed
                     if x['freshness'] in {'recent', 'recent_date_only'}}
    eligible = [x for x in direct if x['freshness'] in {'recent', 'recent_date_only'}]
    eligible.sort(key=lambda x: (normalized_title(x['title'], source['name']) not in feed_by_title, direct.index(x)))
    # Unknown-date articles may be diagnosed, but never counted as recent.
    if not eligible:
        eligible = [x for x in direct if x['freshness'] == 'unknown']
    sample = [(x, 'direct') for x in eligible[:2]]
    if source['collection_method'] == 'Google News RSS' and sample:
        other = feed_by_title.get(normalized_title(sample[0][0]['title'], source['name']))
        if other and host(other['url']) == 'news.google.com':
            sample.append((other, 'paired_google_wrapper'))
    return sample


def retrieve_samples(out=OUT):
    if (out / 'retrieval.json').exists():
        raise SystemExit('retrieval.json already exists; refusing an accidental repeat of live requests')
    ledger, results, stopped = RequestLedger(), [], set()
    plans = []
    for source in sources(out):
        direct = read(out / 'direct' / (slug(source['name']) + '.json'))
        if source['name'] in EXCLUDED or source['name'] == 'Saudi Press Agency' or direct['fetch']['status'] != 'fetched':
            continue
        feed = read(out / 'feeds' / (slug(source['name']) + '.json'))
        plans.append((source, retrieval_sample(source, direct['accepted'], feed['entries'])))
    # Round-robin: every source gets its first test before any gets a second.
    for turn in range(3):
        for source, plan in plans:
            if len(ledger.requests) >= ledger.limit:
                break
            if turn >= len(plan) or source['name'] in stopped:
                continue
            item, method = plan[turn]
            row = retrieve_one(item, source, ledger, out=out)
            row['method'] = method
            results.append(row)
            print(source['name'], method, row['raw_status'], row['audited_status'], 'requests', row['requests'], flush=True)
            if row['raw_status'] == 'blocked' or row['audited_status'] == 'blocked_or_paywalled':
                stopped.add(source['name'])
            write(out / 'retrieval.json', {'request_limit': ledger.limit, 'network_requests': len(ledger.requests),
                                          'requests': ledger.requests, 'results': results, 'stopped_publishers': sorted(stopped)})


def diagnose_spa(out=OUT):
    """Explain the cached shell using only the page already downloaded."""
    path = out / 'pages/saudi_press_agency.html'
    if not path.exists():
        write(out / 'spa_diagnostic.json', {'status': 'no_cached_page'})
        return
    tree = lhtml.fromstring(path.read_bytes().decode('utf8', errors='replace'))
    raw = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    data = json.loads(raw[0]) if raw else {}
    news = data.get('props', {}).get('pageProps', {}).get('mainNews', [])
    items = [{'uuid': x.get('uuid'), 'title': x.get('title'), 'published_at': x.get('published_at'),
              'explicit_article_url': x.get('url') or x.get('link')} for x in news if isinstance(x, dict)]
    write(out / 'spa_diagnostic.json', dict(anchors=len(tree.xpath('//a[@href]')),
          empty_next_root=bool(tree.xpath('//*[@id="__next" and not(node())]')),
          next_data_present=bool(raw), main_news_records=len(items), sample=items[:3],
          runtime_config_keys=sorted(data.get('runtimeConfig', {}).keys()),
          conclusion='Next.js shell with embedded English news records, but no explicit article links. No UUID-to-URL routes guessed and no API requests made.',
          next_step='Validate the public article route before a separate bounded embedded-JSON discovery experiment; no browser needed to inspect the supplied metadata.'))


def verify(out=OUT):
    before = read(out / 'protected_before.json')
    changed = [name for name, digest in before.items() if not (ROOT / name).exists() or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    result = dict(protected_files=len(before), changed_preexisting_files=changed,
                  ingestion_state_files=sum(name.startswith('.local_state') for name in before),
                  llm_requests=0, paid_api_cost_usd=0, notion_writes=0,
                  article_http_requests=read(out / 'retrieval.json')['network_requests'])
    write(out / 'integrity.json', result)
    print(json.dumps(result))
    if changed:
        raise SystemExit('pre-existing file integrity failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['snapshot', 'fetch-listings', 'analyze', 'fetch-feeds', 'compare', 'retrieve', 'diagnose-spa', 'verify'])
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    {'snapshot': snapshot, 'fetch-listings': fetch_listings, 'analyze': analyze, 'fetch-feeds': fetch_feeds,
     'compare': comparison, 'retrieve': retrieve_samples, 'diagnose-spa': diagnose_spa, 'verify': verify}[args.stage](args.out)

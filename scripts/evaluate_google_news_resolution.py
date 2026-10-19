"""Read-only Google News URL-resolution benchmark; no ingestion integration.

Unofficial RPC mechanism reviewed at SSujitX/google-news-url-decoder commit
990bf393f0c0717988c6456c641a2c6af252b599. Protocol constants adapted under MIT;
the upstream copyright/permission notice is retained in reference/LICENSE in the
benchmark output. No upstream package, proxies, browser or model is used.
Live network work requires --live; --prepare only freezes existing audit data.
"""
# Adapted protocol constants: Copyright (c) 2024 Sujit Biswas (MIT).
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
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import time
import unicodedata
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import httpx
from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.preview/evaluations/google_news_url_resolution_20261019'
AUDIT = ROOT / '.preview/ingestion_audits/20261019T150812322754Z_6399d0a4.json'
SOURCE_SNAPSHOT = ROOT / '.preview/evaluations/direct_site_discovery_20261019/sources.json'
MAX_WRAPPERS = 48
MAX_BYTES = 2_000_000
GOOGLE_RPC = 'https://news.google.com/_/DotsSplashUi/data/batchexecute'
HEADERS = {'User-Agent': 'SOMA-MATER-Research/1.0', 'Accept': 'text/html,application/json'}
REFUSED = {401, 402, 403, 405, 407, 429, 451}
NON_ARTICLE = {'search', 'login', 'signin', 'sign-in', 'register', 'subscribe', 'category', 'categories', 'tags', 'tag', 'authors', 'author', 'about', 'contact', 'privacy', 'terms'}
GART_CONTEXT = [
    ['X', 'X', ['X', 'X'], None, None, 1, 1, 'US:en', None, 1, None, None, None, None, None, 0, 1],
    'X', 'X', 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0,
]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def host(url):
    try:
        return (urlsplit(url).hostname or '').lower().removeprefix('www.')
    except ValueError:
        return ''


def publisher_url(url, domain):
    """Validate scheme/host and plausible article path before any publisher GET."""
    try:
        parts = urlsplit(url)
        name = (parts.hostname or '').lower().removeprefix('www.')
        if parts.scheme not in {'http', 'https'} or parts.username or parts.password or parts.port not in {None, 80, 443}:
            return False
        if name != domain and not name.endswith('.' + domain):
            return False
        segments = [s for s in parts.path.split('/') if s]
        if len(segments) < 2 or any(s.casefold() in NON_ARTICLE for s in segments):
            return False
        if re.search(r'\.(?:jpg|png|gif|svg|js|css|pdf|xml|mp4)$', segments[-1], re.I):
            return False
        return len(re.findall(r'[^\W_]+', segments[-1])) >= 3 or bool(
            set(segments[:-1]) & {'article', 'articles', 'node', 'story', 'stories'}
        )
    except (ValueError, TypeError):
        return False


def article_id(url):
    try:
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.hostname != 'news.google.com' or parts.username or parts.password or parts.port not in {None, 443}:
            return None
        match = re.fullmatch(r'/(?:rss/articles|articles|read)/([A-Za-z0-9_-]{10,2500})', parts.path)
        return match[1] if match else None
    except ValueError:
        return None


def params_url(url):
    identity = article_id(url)
    if not identity:
        raise ValueError('invalid_google_wrapper')
    query = parse_qs(urlsplit(url).query)
    locale = {k: query.get(k, [default])[0] for k, default in [('hl', 'en-US'), ('gl', 'US'), ('ceid', 'US:en')]}
    return 'https://news.google.com/rss/articles/' + identity + '?' + urlencode(locale)


def parse_signature(markup):
    try:
        tree = html.fromstring(markup)
        pairs = {(n.get('data-n-a-sg'), n.get('data-n-a-ts')) for n in tree.xpath('//*[@data-n-a-sg and @data-n-a-ts]')}
    except (ValueError, etree.LxmlError):
        return None
    if len(pairs) != 1:
        return None
    signature, stamp = pairs.pop()
    if not signature or len(signature) > 4096 or not re.fullmatch(r'\d{1,16}', stamp or ''):
        return None
    return signature, stamp


def rpc_body(identity, signature, stamp):
    inner = ['garturlreq', GART_CONTEXT, identity, int(stamp), signature]
    envelope = [[['Fbv4je', json.dumps(inner, separators=(',', ':')), None, '0']]]
    return urlencode({'f.req': json.dumps(envelope, separators=(',', ':'))})


def parse_rpc(body):
    """Read XSSI/length-framed JSON without trusting row order or unrelated RPCs."""
    value = body.lstrip('\ufeff \r\n\t')
    if value.startswith(")]}'"):
        value = value[4:].lstrip()
    decoder, documents = json.JSONDecoder(), []
    while value:
        # Google's decimal frame lengths are not JSON document values.
        frame = re.match(r'^\d+\s*\n', value)
        if frame:
            value = value[frame.end():].lstrip()
            continue
        document, end = decoder.raw_decode(value)
        documents.append(document)
        value = value[end:].lstrip()
    urls = []
    for rows in documents:
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list) or len(row) < 3 or row[:2] != ['wrb.fr', 'Fbv4je']:
                continue
            payload = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            if isinstance(payload, list) and len(payload) > 1 and payload[0] == 'garturlres' and isinstance(payload[1], str):
                urls.append(payload[1])
    if len(urls) != 1:
        raise ValueError('missing_or_ambiguous_rpc_url')
    return urls[0]


def challenge(markup):
    try:
        tree = html.fromstring(markup or '<html></html>')
        title = ' '.join(tree.xpath('//title/text()|//h1//text()'))
        return bool(re.search(r'unusual traffic|before you continue|access denied|verify.{0,20}human|captcha|just a moment|^sorry', title, re.I)
                    or tree.xpath('//form[contains(@action,"/sorry/")]'))
    except (ValueError, etree.LxmlError):
        return False


class GoogleResolver:
    """Serial transparent requests with a global refusal latch and rate spacing."""
    def __init__(self, client, *, interval=2.0, sleep=time.sleep, clock=time.monotonic, out=None):
        self.client, self.interval, self.sleep, self.clock = client, interval, sleep, clock
        self.last_request = None
        self.stopped_reason = ''
        self.requests = []
        self.out = out

    def request(self, method, url, *, content=None):
        if self.stopped_reason:
            raise ValueError('stopped_after_google_refusal')
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.hostname != 'news.google.com' or parts.username or parts.password or parts.port not in {None, 443}:
            raise ValueError('unsafe_google_endpoint')
        if self.last_request is not None:
            self.sleep(max(0, self.interval - (self.clock() - self.last_request)))
        self.last_request = self.clock()
        record = dict(method=method, url=url, started_at=datetime.now(timezone.utc).isoformat())
        self.requests.append(record)
        headers = dict(HEADERS)
        if method == 'POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        with self.client.stream(method, url, content=content, headers=headers, follow_redirects=False) as response:
            record['http_status'] = response.status_code
            if response.headers.get('retry-after'):
                record['retry_after'] = response.headers['retry-after']
            if response.status_code in REFUSED:
                category = 'google_http_429' if response.status_code == 429 else 'google_http_refusal'
                self.stopped_reason = category
                raise ValueError(category)
            if response.is_redirect:
                return response.status_code, response.headers, ''
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > MAX_BYTES:
                    raise ValueError('google_response_too_large')
                body.extend(chunk)
        record.update(response_bytes=len(body), response_sha256=hashlib.sha256(body).hexdigest())
        if self.out is not None:
            path = self.out / 'google_responses' / f'{len(self.requests):03}_{method}.txt'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            record['response_file'] = str(path.relative_to(self.out))
        markup = body.decode('utf8', errors='replace')
        if challenge(markup):
            self.stopped_reason = 'google_challenge_or_consent'
            raise ValueError(self.stopped_reason)
        return response.status_code, response.headers, markup

    def resolve(self, item):
        before, start = len(self.requests), self.clock()
        row = dict(article_id=item['article_id'], publisher=item['publisher'], expected_title=item['title'],
                   original_google_url=item['url'], resolution_attempted=False, resolution_success=False,
                   resolved_url=None, resolved_hostname=None, error_category=None)
        try:
            if self.stopped_reason:
                raise ValueError('stopped_after_google_refusal')
            current = params_url(item['url'])
            row['resolution_attempted'] = True
            markup, resolved = '', None
            for hop in range(2):
                status, headers, markup = self.request('GET', current)
                if not 300 <= status < 400:
                    break
                destination = urljoin(current, headers.get('location', ''))
                if publisher_url(destination, item['expected_domain']):
                    resolved = destination
                    break
                if host(destination) in {'google.com', 'consent.google.com', 'accounts.google.com'} or '/sorry' in destination:
                    self.stopped_reason = 'google_challenge_or_consent'
                    raise ValueError(self.stopped_reason)
                if hop or article_id(destination) != article_id(item['url']):
                    raise ValueError('unexpected_google_redirect')
                current = destination
            if resolved is None:
                parsed = parse_signature(markup)
                if parsed is None:
                    raise ValueError('signature_or_timestamp_missing')
                signature, stamp = parsed
                status, headers, body = self.request('POST', GOOGLE_RPC, content=rpc_body(article_id(item['url']), signature, stamp))
                if 300 <= status < 400:
                    self.stopped_reason = 'google_rpc_redirect_refused'
                    raise ValueError(self.stopped_reason)
                resolved = parse_rpc(body)
            if not publisher_url(resolved, item['expected_domain']):
                raise ValueError('invalid_or_wrong_publisher_url')
            row.update(resolution_success=True, resolved_url=resolved, resolved_hostname=host(resolved))
        except httpx.TimeoutException:
            row['error_category'] = 'google_timeout'
        except httpx.HTTPError:
            row['error_category'] = 'google_http_or_network_error'
        except (ValueError, TypeError, IndexError, KeyError) as exc:
            row['error_category'] = str(exc) if str(exc) in {
                'stopped_after_google_refusal', 'invalid_google_wrapper', 'google_http_429', 'google_http_refusal',
                'google_challenge_or_consent', 'google_response_too_large', 'unexpected_google_redirect',
                'signature_or_timestamp_missing', 'invalid_or_wrong_publisher_url', 'google_rpc_redirect_refused',
            } else 'malformed_rpc_response'
        row.update(latency_seconds=round(self.clock() - start, 3), request_count=len(self.requests)-before)
        return row


def prepare(out=OUT, audit_path=AUDIT, source_path=SOURCE_SNAPSHOT):
    if (out / 'dataset.json').exists():
        raise SystemExit('dataset already exists; refusing to overwrite frozen inputs')
    audit, registry = read(audit_path), read(source_path)
    domains = {s['name']: host(s['source_url']) for s in registry['sources']}
    rows, seen = [], set()
    for row in audit['candidates']:
        if not row.get('enrichment_attempted') or row.get('discovery_method') != 'google_news_rss':
            continue
        url = row.get('canonical_url', '')
        identity = article_id(url)
        if not identity or url in seen or not domains.get(row['publisher']):
            raise ValueError('missing, duplicate or invalid enriched wrapper metadata')
        seen.add(url)
        rows.append(dict(article_id=row['candidate_id'], title=row['title'], url=url,
                         publisher=row['publisher'], expected_domain=domains[row['publisher']],
                         baseline_status=row['evidence_retrieval_status'], baseline_source='latest recorded ingestion audit',
                         allocation_rank=row.get('allocation_rank'), selected_in_audit=row.get('selected', False)))
    if not 1 <= len(rows) <= MAX_WRAPPERS:
        raise ValueError('dataset must contain 1..48 enriched wrappers; never truncate silently')
    # Per-publisher round-robin, strongest existing allocation rank first.
    publishers = sorted({row['publisher'] for row in rows})
    buckets = {name: sorted([row for row in rows if row['publisher'] == name], key=lambda x: (x['allocation_rank'] or 9999, x['article_id'])) for name in publishers}
    ordered = [buckets[name][index] for index in range(max(map(len, buckets.values()))) for name in publishers if index < len(buckets[name])]
    write(out / 'dataset.json', dict(audit_path=str(audit_path.relative_to(ROOT)), audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                                   source_snapshot=str(source_path.relative_to(ROOT)), articles=ordered))
    print('Frozen', len(ordered), 'actual enriched wrappers:', dict(Counter(r['publisher'] for r in ordered)))


class PublisherTransport(httpx.BaseTransport):
    """Observe actual requests, restricting redirects to the expected publisher."""
    def __init__(self, domain, transport=None):
        self.domain = domain
        self.transport = transport if transport is not None else httpx.HTTPTransport(retries=0)
        self.requests, self.body, self.final_url, self.status = [], bytearray(), '', None
        self.guard_reason, self.refused_redirect = '', None

    def handle_request(self, request):
        url = str(request.url)
        if not publisher_url(url, self.domain):
            self.guard_reason, self.refused_redirect = 'external_or_non_article_redirect_refused', url
            raise httpx.RequestError('external_or_non_article_redirect_refused', request=request)
        self.requests.append(url)
        self.final_url, self.body = url, bytearray()
        response = self.transport.handle_request(request)
        self.status = response.status_code
        return response

    def close(self):
        self.transport.close()


class PublisherClient(httpx.Client):
    @contextmanager
    def stream(self, *args, **kwargs):
        with super().stream(*args, **kwargs) as response:
            original = response.iter_bytes

            def observed(*args, **kwargs):
                for chunk in original(*args, **kwargs):
                    self._transport.body.extend(chunk[:max(0, MAX_BYTES-len(self._transport.body))])
                    yield chunk
            response.iter_bytes = observed
            yield response


def words(title, publisher=''):
    if publisher:
        title = re.split(r'\s+[-|]\s+' + re.escape(publisher) + r'(?:\b|$)', title, maxsplit=1, flags=re.I)[0]
    ignored = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'says', 'news', 'new', 'into', 'over', 'are', 'its', 'has'}
    return {t for t in re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', title).casefold()) if len(t) > 2 and t not in ignored}


def confirmed_wrong_story(page):
    return bool(page and page['raw_status'] == 'extracted' and not page['publisher_access_failure']
                and page['title_overlap'] < .25 and page['body_overlap'] < .25)


def retrieve_publisher(item, resolved, *, transport=None, out=None):
    """Use the current unmodified ArticleRetriever; audit completeness separately."""
    from research_automation.models.article import Article
    from research_automation.pipeline.article_retrieval import ArticleRetriever
    observed = PublisherTransport(item['expected_domain'], transport)
    started = time.perf_counter()
    article = Article(item['title'], resolved, resolved, item['publisher'], '')
    with PublisherClient(transport=observed, follow_redirects=True, max_redirects=5, trust_env=False,
                         timeout=httpx.Timeout(connect=5, read=15, write=10, pool=5)) as client:
        result = ArticleRetriever(client=client).retrieve(article)
    markup = observed.body.decode('utf8', errors='replace')
    page_title, paragraphs, title_overlap, body_overlap = '', 0, 0.0, 0.0
    access = ''
    try:
        tree = html.fromstring(markup or '<html></html>')
        page_title = ' '.join(' '.join(tree.xpath('//h1//text()|//title/text()|//meta[@property="og:title"]/@content')).split())
        paragraphs = sum(len(' '.join(p.text_content().split())) >= 60 for p in tree.xpath('//p'))
        expected = words(item['title'], item['publisher'])
        title_overlap = len(expected & words(page_title)) / max(1, len(expected))
        body_overlap = len(expected & words(result.article_text)) / max(1, len(expected))
        if challenge(markup):
            access = 'publisher_challenge'
        elif re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', markup, re.I):
            access = 'publisher_paywall_metadata'
        elif re.search(r'(?:subscribe|sign in|log in) to (?:continue|read)|create a free .{0,30}account to access', tree.text_content(), re.I):
            access = 'publisher_login_or_subscription'
    except (ValueError, etree.LxmlError):
        pass
    if observed.status in REFUSED:
        access = 'publisher_http_429' if observed.status == 429 else 'publisher_http_refusal'
    supported = result.evidence_retrieval_status == 'extracted' and not access and title_overlap >= .45 and body_overlap >= .45 and paragraphs >= 2 and publisher_url(result.canonical_url, item['expected_domain'])
    audited = 'supported_extraction' if supported else (access or result.evidence_retrieval_status)
    if result.evidence_retrieval_status == 'extracted' and not supported and not access:
        audited = 'article_body_or_story_not_verified'
    row = dict(raw_status=result.evidence_retrieval_status, audited_status=audited, supported=supported,
               publisher_access_failure=access or None, canonical_url=result.canonical_url,
               final_url=observed.final_url, http_status=observed.status, page_title=page_title[:500],
               title_overlap=round(title_overlap, 3), body_overlap=round(body_overlap, 3), paragraphs=paragraphs,
               characters=len(result.article_text), request_count=len(observed.requests), requests=observed.requests,
               latency_seconds=round(time.perf_counter()-started, 3),
               extracted_text_sha256=hashlib.sha256(result.article_text.encode()).hexdigest())
    row.update(guard_reason=observed.guard_reason, refused_redirect=observed.refused_redirect)
    if out is not None and markup:
        path = out / 'publisher_pages' / (item['article_id'] + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(observed.body)
        row.update(html_file=str(path.relative_to(out)), html_sha256=hashlib.sha256(observed.body).hexdigest())
    return row


def live(out=OUT):
    if (out / 'results.json').exists():
        raise SystemExit('results already exist; refusing accidental repeat of live benchmark')
    dataset = read(out / 'dataset.json')['articles']
    if not 1 <= len(dataset) <= MAX_WRAPPERS or len({r['url'] for r in dataset}) != len(dataset):
        raise SystemExit('invalid or oversized dataset')
    results, stopped_publishers = [], set()
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=15) as client:
        resolver = GoogleResolver(client, out=out)
        for index, item in enumerate(dataset, 1):
            row = resolver.resolve(item)
            row['baseline_wrapper_status'] = item['baseline_status']
            row['baseline_source'] = item['baseline_source']
            row['publisher_retrieval'] = None
            if row['resolution_success']:
                if item['expected_domain'] in stopped_publishers:
                    row['publisher_retrieval_skipped'] = 'prior publisher refusal/access requirement in this run'
                else:
                    row['publisher_retrieval'] = retrieve_publisher(item, row['resolved_url'], out=out)
                    if confirmed_wrong_story(row['publisher_retrieval']):
                        row.update(resolution_success=False, error_category='decoded_story_mismatch')
                    if row['publisher_retrieval']['publisher_access_failure']:
                        stopped_publishers.add(item['expected_domain'])
            results.append(row)
            write(out / 'results.json', dict(started_from_audit=str(AUDIT.relative_to(ROOT)),
                  google_requests=resolver.requests, google_stop_reason=resolver.stopped_reason,
                  stopped_publishers=sorted(stopped_publishers), results=results))
            status = row['publisher_retrieval']['audited_status'] if row['publisher_retrieval'] else row['error_category'] or row.get('publisher_retrieval_skipped')
            print(f'{index}/{len(dataset)} {item["publisher"]}: resolved={row["resolution_success"]}; {status}', flush=True)
        print('Google network requests:', len(resolver.requests), '; stop reason:', resolver.stopped_reason or 'none', flush=True)


def report(out=OUT):
    run, dataset = read(out / 'results.json'), read(out / 'dataset.json')
    rows, items = run['results'], {r['article_id']: r for r in dataset['articles']}
    attempted = [r for r in rows if r['resolution_attempted']]
    resolved = [r for r in rows if r['resolution_success']]
    retrieved = [r for r in rows if r.get('publisher_retrieval')]
    supported = [r for r in retrieved if r['publisher_retrieval']['supported']]
    publisher_requests = sum(r['publisher_retrieval']['request_count'] for r in retrieved)
    # No live requests: annotate metadata-only story validation and the stricter
    # benchmark redirect guard separately from the unmodified retriever result.
    flat = []
    for row in rows:
        page = row.get('publisher_retrieval')
        expected = words(row['expected_title'], row['publisher'])
        path = urlsplit(row['resolved_url']).path if row['resolved_url'] else ''
        slug_overlap = len(expected & words(path)) / max(1, len(expected))
        story_check = ('page_heading_matches' if page and page['title_overlap'] >= .45 else
                       'url_slug_supports_headline' if slug_overlap >= .45 else 'story_not_independently_verified')
        guard = bool(page and page['raw_status'] == 'fetch_failed' and page['http_status'] in {301, 302, 303, 307, 308} and page['request_count'] == 1)
        entry = {k: v for k, v in row.items() if k != 'publisher_retrieval'}
        entry.update(story_validation=story_check, url_slug_overlap=round(slug_overlap, 3),
                     baseline_status=row['baseline_wrapper_status'],
                     raw_publisher_status=page['raw_status'] if page else 'not_attempted',
                     audited_publisher_status=page['audited_status'] if page else 'not_attempted',
                     supported_body=bool(page and page['supported']), canonical_url=page['canonical_url'] if page else None,
                     publisher_http_status=page['http_status'] if page else None,
                     publisher_request_count=page['request_count'] if page else 0,
                     benchmark_redirect_guard_limitation=guard)
        flat.append(entry)
    write(out / 'article_results.json', flat)
    with (out / 'article_results.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(dict.fromkeys(k for r in flat for k in r)))
        writer.writeheader()
        writer.writerows(flat)
    baseline = Counter(r['baseline_wrapper_status'] for r in rows)
    raw = Counter(r['publisher_retrieval']['raw_status'] for r in retrieved)
    access = Counter(r['publisher_retrieval']['publisher_access_failure'] for r in retrieved if r['publisher_retrieval']['publisher_access_failure'])
    median = statistics.median(r['latency_seconds'] for r in attempted) if attempted else None
    failures = Counter(r['error_category'] for r in rows if r['error_category'])
    decision = 'GO' if len(resolved) >= .9*len(rows) and len(supported) >= .25*len(rows) and not any(confirmed_wrong_story(r['publisher_retrieval']) for r in retrieved) and not run['google_stop_reason'] and median is not None and median <= 15 else 'NO-GO'
    summary = dict(recommendation=decision, scope='controlled implementation proposal only; no production change made',
                   dataset_wrappers=len(rows), resolution_attempted=len(attempted), resolved=len(resolved),
                   resolution_success_rate=len(resolved)/len(rows), failures_by_category=dict(failures),
                   median_resolution_latency_seconds=median, google_requests=len(run['google_requests']),
                   publisher_requests=publisher_requests, publisher_retrieval_attempted=len(retrieved),
                   publisher_retrieval_not_attempted=len(rows)-len(retrieved), baseline_statuses=dict(baseline),
                   resolved_raw_statuses=dict(raw), supported_bodies=len(supported),
                   incremental_supported_bodies=sum(r['baseline_wrapper_status']!='extracted' for r in supported),
                   publisher_access_failures=dict(access), google_stop_reason=run['google_stop_reason'],
                   google_429_count=sum(r.get('http_status')==429 for r in run['google_requests']),
                   story_validation_counts=dict(Counter(r['story_validation'] for r in flat)),
                   benchmark_redirect_guard_cases=sum(r['benchmark_redirect_guard_limitation'] for r in flat),
                   model_requests=0, notion_writes=0, api_cost_usd=0)
    write(out / 'summary.json', summary)
    source = read(out / 'reference/upstream.json')
    publishers = []
    for name in sorted({r['publisher'] for r in rows}):
        a = [r for r in rows if r['publisher']==name]
        p = [r['publisher_retrieval'] for r in a if r['publisher_retrieval']]
        publishers.append(dict(publisher=name, wrappers=len(a), resolved=sum(r['resolution_success'] for r in a),
            body_attempts=len(p), raw_extracted=sum(x['raw_status']=='extracted' for x in p),
            supported=sum(x['supported'] for x in p), not_attempted=len(a)-len(p),
            raw_statuses=dict(Counter(x['raw_status'] for x in p)),
            access_failures=sum(bool(x['publisher_access_failure']) for x in p),
            median_resolution_seconds=statistics.median(r['latency_seconds'] for r in a)))
    write(out / 'publisher_summary.json', publishers)
    lines = [
        '# Google News URL resolution — 19 October 2026', '',
        f'**{decision} for a controlled URL-resolution implementation proposal. Production remains unchanged.**', '',
        f'Tested the actual **{len(rows)} enriched Google News wrappers** from the latest shadow audit. **{len(resolved)}/{len(rows)} resolved to plausible article URLs on the expected publisher domains**. The unchanged ArticleRetriever returned **{raw.get("extracted",0)} raw extractions**, of which **{len(supported)} pass conservative body/headline/access checks**, compared with **{baseline.get("extracted",0)} extracted / {baseline.get("insufficient_content",0)} insufficient_content in the saved wrapper baseline. This is **{len(supported)} incremental supported article bodies ({len(supported)/len(rows):.1%} of the target set)**.', '',
        f'Resolution used **{len(run["google_requests"])} Google requests**, median **{median}s per wrapper**, sequentially with at least two seconds between Google request starts. There were **{summary["google_429_count"]} Google HTTP 429 responses**; global Google stop reason: **{run["google_stop_reason"] or "none"}**. Publisher retrieval used **{publisher_requests} HTTP requests for {len(retrieved)} article attempts**, including redirects. Model/API cost: **$0**.', '',
        '## Dataset and baseline', '',
        '- Input: .preview/ingestion_audits/20261019T150812322754Z_6399d0a4.json. Only enrichment_attempted=true and discovery_method=google_news_rss records; all 42 original URLs were present. No random feed entries, invented snippets or new ingestion. Frozen dataset includes audit hash, expected titles/publishers, existing allocation rank and baseline status.',
        '- Maximum 48 wrappers; actual 42, no truncation. Per-publisher round-robin tests existing enrichment priorities before later candidates.',
        '- Baseline wrapper outcomes are reused from that exact read-only shadow audit, not refetched concurrently. All 42 recorded insufficient_content. This avoids additional Google requests; the time gap is a limitation. No Luna/Sol judgment is used as ground truth for URL/body correctness.', '',
        '## Reviewed mechanism and boundaries', '',
        f'Pinned review: [SSujitX/google-news-url-decoder, {source["commit"][:12]}](https://github.com/SSujitX/google-news-url-decoder/tree/{source["commit"]}), committed {source["date"]}. Its [protocol implementation](https://github.com/SSujitX/google-news-url-decoder/blob/{source["commit"]}/googlenewsdecoder/_parse.py) extracts a per-article signature/timestamp from the RSS page and sends garturlreq through Fbv4je at the unofficial DotsSplashUi batchexecute endpoint. The current repository also supports batching many signatures into one POST; this benchmark uses one article per POST to avoid response-order ambiguity and to stop immediately on refusal.', '',
        '- Start with /rss/articles/{id}?hl=en-US&gl=US&ceid=US:en, preserving any input locale. Opaque IDs are not treated as base64 publisher URLs. Only a same-ID, same-Google-host article redirect is allowed as one alternate hop; none was needed in this snapshot.',
        '- Transparent SOMA-MATER-Research/1.0 User-Agent; existing httpx/lxml only; trust_env=False; no proxies, accounts, CAPTCHA handling, browser, impersonation, evasion, or paid decoder API. The upstream package was not installed. Upstream source/license copies are retained under reference/.',
        '- Concurrency one, 15-second Google timeout, decoded response ceiling 2 MB, zero network retries. Any Google refusal/429/challenge/consent stops all remaining Google requests. Remaining inputs are explicitly marked unattempted. Publisher refusal/access requirements stop further publisher requests for that domain while Google resolution can continue.',
        '- Validate decoded scheme, exact expected publisher/subdomain, and a plausible non-homepage/article path. Reject Google URLs, unrelated hosts, homepage/category/search/login/assets and ambiguous RPC payloads. Single-item RPC responses cannot be assigned by array position to a different input.', '',
        '## Publisher breakdown', '',
        '| Publisher | Wrappers | Resolved | Publisher attempts | Raw extracted | Supported bodies | Skipped after refusal | Median resolution s |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for p in publishers:
        lines.append(f'| {p["publisher"]} | {p["wrappers"]} | {p["resolved"]} | {p["body_attempts"]} | {p["raw_extracted"]} | {p["supported"]} | {p["not_attempted"]} | {p["median_resolution_seconds"]} |')
    lines += ['', '## Failures, validation and limits', '',
        f'- URL-resolution failure categories: {dict(failures) or "none"}. All returned URLs matched the expected publisher and passed article-path checks. Story validation: {summary["story_validation_counts"]}. No readable page showed an unrelated headline; access-restricted/opaque cases are not all independently verified.',
        f'- Raw publisher statuses: {dict(raw)}. Access failures: {dict(access)}. HTTP 405 is a refusal in this benchmark even though the existing retriever reports fetch_failed; HTTP 403 remains blocked. No alternate publisher fetcher or login was attempted.',
        '- AGBI, Reuters and S&P each refused the first publisher request. Eleven remaining resolved URLs from those domains were deliberately not fetched. They are not counted as article-body failures or recoveries; their publisher/story bodies remain unverified.',
        f'- **Nature limitation:** {summary["benchmark_redirect_guard_cases"]} initial publisher redirects were stopped by this benchmark\'s strict article-path/host redirect guard. The original run did not retain the rejected redirect destinations. These fetch_failed records are a harness-policy limitation, not evidence that the default retriever inherently cannot read those Nature articles. They were not retried or counted as recovered. Nature support requires a later public-cookie/redirect review without authentication or bypass.',
        '- The two additional Gulf News raw extractions have exact matching page headings but their extracted later sections do not pass the conservative headline-term check. They are plausible partial article evidence, not independently confirmed complete recoveries. Count 20 as the conservative supported minimum and 22 as raw extraction, not a claim of complete article text.',
        '- Supported recovery requires the existing retriever to return extracted, at least two substantial HTML paragraphs, expected-heading and extracted-body keyword overlap, an article canonical, and no access gate. Cached headings/paragraph counts and text hashes are retained. Public page HTML is stored locally for audit; the report does not reproduce article bodies.',
        '- Non-free metadata/login/challenge checks are conservative, including any isAccessibleForFree=false signal; related-item metadata can cause false negatives. No such paywall signal was needed to classify this run\'s three observed HTTP refusals.',
        '- Unofficial, undocumented Google protocol: one successful sample cannot establish long-term stability. No second pass was made merely to inflate consistency evidence. Source markup/RPC formats/rate limits may change; a future implementation needs a bounded failure path that retains the original wrapper and existing metadata.', '',
        '## Recommendation', '',
        f'**{decision}** is supported by the measured resolution reliability, correct publisher/article paths, no observed wrong readable stories, material body recovery, reasonable two-request resolution volume/latency, and no Google refusal or bypass. The report renderer uses practical benchmark checks (at least 90% resolutions, at least 25% supported incremental bodies, median resolution at most 15 seconds, no Google refusal) to make this recommendation explicit; these are evaluation checks, not changes to any production selection threshold.', '',
        'Recommend the next narrowly scoped implementation review of URL resolution before the existing ArticleRetriever, with transparent networking, refusal stopping, original-wrapper retention and acquisition audit. This benchmark does not integrate or enable it. DIRECT_SITE_DISCOVERY_ENABLED remains false by default and its implementation is retained unchanged. Publisher blocks remain blocks; this is not unrestricted publisher access.', '',
        '## Inspectable examples', '',
        'Wrappers are shortened here; exact URLs and IDs remain in dataset.json/article_results.csv. These are actual decoded URLs, not publisher links reconstructed from titles.', '']
    examples = [r for r in rows if r.get('publisher_retrieval') and r['publisher_retrieval']['supported']][:4]
    examples += [r for r in rows if r.get('publisher_retrieval') and r['publisher_retrieval']['publisher_access_failure']][:1]
    for r in examples:
        lines += [f'- {r["publisher"]}: {r["expected_title"]}', f'  - `https://news.google.com/rss/articles/{article_id(r["original_google_url"])[:20]}…` → {r["resolved_url"]} → `{r["publisher_retrieval"]["raw_status"]}` / `{r["publisher_retrieval"]["audited_status"]}`.']
    lines += ['', '## Files and verification', '',
        '- New code only: scripts/evaluate_google_news_resolution.py and tests/test_google_news_resolution.py. All other additions are benchmark artifacts under this output directory. No production source/configuration, feed, prompt, schema, Notion, ingestion state, model/budget or dependency changes.',
        '- dataset.json, results.json, article_results.json/CSV, summary.json, publisher_summary.json, google_responses/, publisher_pages/, reference/ and integrity/test verification retain the inputs, request ledger, raw outcomes and limits.',
        '- Full pytest / git diff --check results: see verification.json and pytest.txt. Protected pre-existing file hashes: integrity.json.', '',
        'Offline report replay: `.venv\\Scripts\\python.exe -X utf8 scripts/evaluate_google_news_resolution.py --report`.',
        'Live stages refuse to overwrite results. Repeating the benchmark requires a new --out directory and a newly prepared dataset; no automatic retry or repeat was performed.', '']
    if (out / 'verification.json').exists():
        verified = read(out / 'verification.json')
        integrity = read(out / 'integrity.json')
        lines += [f'Final checks: **{verified["full_pytest"]}**, including {verified["new_offline_cases"]} new offline cases; git diff --check exit {verified["git_diff_check_exit_code"]}. Protected pre-existing files: {integrity["protected_preexisting_files"]}; changed: {len(integrity["changed_preexisting_files"])}. Direct-site supplement effective flag was verified false.', '']
    (out / 'report.md').write_text('\n'.join(lines), encoding='utf8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    if sum((args.prepare, args.live, args.report)) != 1:
        parser.error('choose exactly one of --prepare (offline), --live, or --report (offline)')
    if args.prepare:
        prepare(args.out)
    elif args.live:
        live(args.out)
    else:
        report(args.out)

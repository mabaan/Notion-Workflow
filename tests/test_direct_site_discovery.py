"""Offline discovery/metadata and real-retriever budget contracts."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import httpx
import pytest

from scripts import evaluate_direct_site_discovery as b


NOW = datetime(2026, 10, 19, 14, tzinfo=timezone.utc)
SOURCE = dict(name='Publisher', source_url='https://publisher.example', feed_url='https://news.google.com/rss/search?q=site:publisher.example', collection_method='Google News RSS')
URL = 'https://publisher.example/news/egypt-expands-water-reuse-capacity'
TITLE = 'Egypt expands water reuse capacity'


def discover(markup):
    return b.extract_candidates(markup, SOURCE, NOW.isoformat())


def card(index=0, date='<time datetime="2026-10-19T10:00:00Z">today</time>'):
    return f'<article><a href="/news/egypt-expands-water-reuse-capacity-{index}"><h2>{TITLE} {index}</h2></a>{date}<p>The new plant will supply treated water to agricultural producers.</p></article>'


def test_article_metadata_survives_navigation_and_duplicate_removal():
    markup = '<nav><a href="/news/ordinary-looking-long-article-slug">Navigation section with a long label</a></nav>' + card() * 2
    result = discover(markup)
    assert len(result['accepted']) == 1
    item = result['accepted'][0]
    assert item['title'] == TITLE + ' 0'
    assert item['freshness'] == 'recent'
    assert item['date_source'] == 'listing_card'
    assert 'agricultural producers' in item['snippet']
    assert result['duplicate_links'] == 1
    assert result['rejected']['navigation'] == 1


@pytest.mark.parametrize('path', ['/login', '/authors/long-author-profile-name', '/en/topic/green-energy-news', '/category/green-energy-industry-news', '/assets/long-image-file-name.jpg', '/job/deputy-editor-nature-journal', '/collections/most-creative-people-in-business', '/event/public-water-security-discussion', '/world/picture/2026/oct/19/a-photo-feature'])
def test_non_article_link_types_are_rejected(path):
    result = discover(f'<a href="{path}">{TITLE}</a>')
    assert result['accepted'] == []


def test_same_publisher_subdomains_allowed_but_external_and_unsafe_links_rejected():
    for url in ['https://evil.example/news/a-long-enough-story-slug', 'https://publisher.example.evil.example/news/a-long-story-slug', 'javascript:alert(1)', 'http://127.0.0.1/news/a-long-story-slug']:
        assert not b.same_publisher(url, SOURCE['source_url'])
    assert b.same_publisher('https://news.publisher.example/story/a-long-slug', SOURCE['source_url'])


def test_bounds_apply_after_cheap_navigation_rejection():
    result = discover('<nav>' + '<a href="/news">News</a>' * 200 + '</nav>' + ''.join(card(i) for i in range(80)))
    assert len(result['accepted']) == 50
    assert result['considered'] == 50
    assert result['cap_reached']
    result = discover(card() * 120 + card(1))
    assert len(result['accepted']) == 1
    assert result['considered'] == 100


def test_dates_do_not_bleed_between_adjacent_articles():
    result = discover('<div>' + card(0) + card(1, '') + '</div>')
    assert result['accepted'][0]['freshness'] == 'recent'
    assert result['accepted'][1]['published_at'] is None


def test_site_wide_json_date_does_not_date_an_undated_article():
    obj = {'@type': 'WebPage', 'url': SOURCE['source_url'], 'datePublished': '2026-10-19T10:00:00Z'}
    result = discover('<script type="application/ld+json">' + json.dumps(obj) + '</script>' + card(0, ''))
    assert result['accepted'][0]['published_at'] is None


def test_embedded_article_json_uses_exact_url_and_first_publication_date():
    obj = {'url': URL + '-0', 'first-published-at': 1792391760000, 'published-at': 1792400000000, 'subheadline': 'An existing summary with enough actual article detail for an editor.'}
    item = discover('<script type="application/json">' + json.dumps(obj) + '</script>' + card(0, ''))['accepted'][0]
    assert item['date_raw'] == '1792391760000'
    assert item['freshness'] == 'recent'
    assert item['snippet'] == obj['subheadline']


@pytest.mark.parametrize('raw,precision,expected', [('2h ago', 'relative', '2026-10-19T12:00:00+00:00'), ('1d ago', 'relative', '2026-10-18T14:00:00+00:00'), ('19 October 2026', 'date_only', '2026-10-19T00:00:00+00:00'), ('2026-10-19T16:00:00+04:00', 'timestamp', '2026-10-19T12:00:00+00:00')])
def test_real_date_formats_and_reference_timezone(raw, precision, expected):
    value, actual_precision = b.parse_date(raw, NOW)
    assert actual_precision == precision
    assert value.isoformat() == expected


def test_unknown_unzoned_future_and_boundary_dates_stay_distinct():
    assert b.freshness('', NOW)['freshness'] == 'unknown'
    assert b.freshness('2026-10-19T10:00:00', NOW)['date_precision'] == 'timezone_unknown'
    assert b.freshness('2026-10-20T10:00:00Z', NOW)['freshness'] == 'future'
    assert b.freshness('2026-10-20', NOW)['freshness'] == 'future'
    assert b.freshness('2026-10-16', NOW)['freshness'] == 'boundary_date_only'
    assert b.freshness('2026-10-18', NOW)['freshness'] == 'recent_date_only'


def test_highest_heading_is_title_and_year_in_headline_is_not_a_date():
    item = discover('<a href="/news/egypt-water-capacity-plan-2026"><h2>Egypt water capacity plan for 2026</h2><h3>A secondary description of the plan</h3></a>')['accepted'][0]
    assert item['title'] == 'Egypt water capacity plan for 2026'
    assert item['published_at'] is None


def test_dated_url_is_explicitly_only_date_precision():
    item = discover(f'<a href="/news/2026/10/19/water-capacity-plan-for-egypt">{TITLE}</a>')['accepted'][0]
    assert item['date_source'] == 'literal_url_date'
    assert item['freshness'] == 'recent_date_only'


def test_google_title_repetition_is_not_misreported_as_a_snippet():
    xml = f'''<rss version="2.0"><channel><title>News</title><item><title>{TITLE} - Publisher</title><link>https://news.google.com/rss/articles/id</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate><description><![CDATA[<a href="#">{TITLE} - Publisher</a> Publisher]]></description></item></channel></rss>'''
    item = b.feed_items(xml, SOURCE, NOW.isoformat())['entries'][0]
    assert item['snippet'] == ''
    assert item['wrapper']
    assert item['freshness'] == 'recent'


def test_matching_normalizes_punctuation_unicode_and_publisher_suffix():
    assert b.normalized_title('Egypt’s WATER plan! - Publisher', 'Publisher') == b.normalized_title('Egypt’s water plan')
    assert b.normalized_title('Water plant launches') != b.normalized_title('Water plant planned')


def test_static_fetch_disables_stealth_and_stops_after_refusal(tmp_path):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status=429, headers={})
    result = b.static_fetch(SOURCE, tmp_path, get)
    assert result['status'] == 'blocked'
    assert len(calls) == 1
    kwargs = calls[0][1]
    assert kwargs['impersonate'] is None and kwargs['stealthy_headers'] is False
    assert kwargs['follow_redirects'] is False and kwargs['retries'] == 1
    assert kwargs['headers']['User-Agent'] == 'SOMA-MATER-Research/1.0'


def test_excluded_publishers_never_reach_fetcher(tmp_path):
    for name in b.EXCLUDED:
        result = b.static_fetch(dict(SOURCE, name=name), tmp_path, lambda *a, **k: pytest.fail('must not fetch'))
        assert result['requests'] == 0


def test_cross_publisher_redirect_not_followed(tmp_path):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(status=302, headers={'location': 'https://elsewhere.example/private'})
    result = b.static_fetch(SOURCE, tmp_path, get)
    assert result['status'] == 'unsafe_or_external_redirect'
    assert len(calls) == 1


def test_static_response_byte_limit_aborts_and_is_reported(tmp_path):
    def get(url, **kwargs):
        assert kwargs['content_callback'](b'x' * (b.MAX_BYTES + 1)) == 0
        raise RuntimeError('callback aborted oversized response')
    assert b.static_fetch(SOURCE, tmp_path, get)['status'] == 'too_large'


def test_live_fetch_stages_refuse_to_overwrite_frozen_snapshots(tmp_path):
    for folder, call in [('listing_fetches', b.fetch_listings), ('feeds', b.fetch_feeds)]:
        b.write(tmp_path / folder / 'existing.json', {})
        with pytest.raises(SystemExit, match='snapshot already exists'):
            call(tmp_path)


def test_actual_retriever_budget_counts_redirects_and_stops_before_third_send():
    ledger, sent = b.RequestLedger(limit=2), []

    def respond(request):
        sent.append(str(request.url))
        return httpx.Response(302, headers={'location': str(request.url) + 'x'})
    item = dict(title=TITLE, url=URL, freshness='recent')
    result = b.retrieve_one(item, SOURCE, ledger, httpx.MockTransport(respond))
    assert len(sent) == len(ledger.requests) == 2
    assert result['guard_reason'] == 'request_budget_exhausted'
    assert result['raw_status'] == 'fetch_failed'
    assert b.retrieve_one(item, SOURCE, ledger, httpx.MockTransport(respond))['requests'] == 0


def test_actual_retriever_does_not_follow_external_redirect():
    sent = []

    def respond(request):
        sent.append(str(request.url))
        return httpx.Response(302, headers={'location': 'https://outside.example/some-story'})
    row = b.retrieve_one(dict(title=TITLE, url=URL, freshness='recent'), SOURCE, b.RequestLedger(), httpx.MockTransport(respond))
    assert len(sent) == 1
    assert row['guard_reason'] == 'external_redirect_refused'


def test_existing_retriever_extracts_without_scrapling_or_notion():
    body = '<p>' + ('The new reuse plant supplies agricultural producers with treated water. ' * 7) + '</p>'
    html = f'<html><head><title>{TITLE}</title><link rel="canonical" href="{URL}"></head><body><article><h1>{TITLE}</h1>{body * 3}</article></body></html>'
    result = b.retrieve_one(dict(title=TITLE, url=URL, freshness='recent'), SOURCE, b.RequestLedger(), httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, text=html)))
    assert result['raw_status'] == result['audited_status'] == 'extracted'
    assert result['canonical_url'] == URL
    assert result['requests'] == 1


def test_samples_are_bounded_and_wrapper_pair_reports_the_same_headline():
    direct = discover(''.join(card(i) for i in range(5)))['accepted']
    feed = [dict(direct[3], url='https://news.google.com/rss/articles/id', title=direct[3]['title'] + ' - Publisher')]
    sample = b.retrieval_sample(SOURCE, direct, feed)
    assert len(sample) == 3
    assert sum(method == 'direct' for _, method in sample) == 2
    assert sample[0][0]['title'] == direct[3]['title']
    assert sample[2][1] == 'paired_google_wrapper'


def test_request_budget_cannot_be_increased_above_user_ceiling():
    with pytest.raises(ValueError):
        b.RequestLedger(37)

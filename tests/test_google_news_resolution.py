"""Offline contracts for the unofficial, benchmark-only URL resolver."""
import json
from urllib.parse import parse_qs

import httpx
import pytest

from scripts import evaluate_google_news_resolution as b

ID = 'CBMiOpaqueArticleId0123456789'
URL = 'https://news.google.com/rss/articles/' + ID + '?oc=5'
DIRECT = 'https://publisher.example/news/egypt-expands-water-reuse-capacity'
TITLE = 'Egypt expands water reuse capacity'
ITEM = dict(article_id='fixture', url=URL, publisher='Publisher', title=TITLE, expected_domain='publisher.example')
PARAMS = '<html><c-wiz><div jscontroller="x" data-n-a-sg="signature-value" data-n-a-ts="1792420000"></div></c-wiz></html>'


def rpc(url=DIRECT):
    return ")]}'\n\n" + json.dumps([['wrb.fr', 'Fbv4je', json.dumps(['garturlres', url]), None, '0'], ['di', 1]])


def resolver(response):
    client = httpx.Client(transport=httpx.MockTransport(response))
    return b.GoogleResolver(client, interval=0, sleep=lambda _: None)


def test_modern_resolution_uses_signature_rpc_and_transparent_agent():
    calls = []

    def respond(request):
        calls.append(request)
        if request.method == 'GET':
            assert parse_qs(request.url.query.decode()) == {'hl': ['en-US'], 'gl': ['US'], 'ceid': ['US:en']}
            return httpx.Response(200, text=PARAMS)
        envelope = json.loads(parse_qs(request.content.decode())['f.req'][0])
        inner = json.loads(envelope[0][0][1])
        assert inner[0] == 'garturlreq' and inner[2:] == [ID, 1792420000, 'signature-value']
        assert envelope[0][0][0] == 'Fbv4je'
        return httpx.Response(200, text=rpc())
    r = resolver(respond)
    row = r.resolve(ITEM)
    assert row['resolution_success'] and row['resolved_url'] == DIRECT
    assert row['request_count'] == 2
    assert all(x.headers['user-agent'] == 'SOMA-MATER-Research/1.0' for x in calls)


@pytest.mark.parametrize('status', [401, 403, 405, 429, 451])
def test_google_refusal_stops_every_subsequent_google_request(status):
    calls = []
    r = resolver(lambda request: (calls.append(request) or httpx.Response(status)))
    first = r.resolve(ITEM)
    assert first['error_category'] == ('google_http_429' if status == 429 else 'google_http_refusal')
    second = r.resolve(ITEM)
    assert not second['resolution_attempted'] and second['request_count'] == 0
    assert len(calls) == 1


def test_challenge_redirect_is_not_followed_or_retried():
    calls = []
    r = resolver(lambda request: (calls.append(request) or httpx.Response(302, headers={'location': 'https://www.google.com/sorry/index'})))
    assert r.resolve(ITEM)['error_category'] == 'google_challenge_or_consent'
    assert not r.resolve(ITEM)['resolution_attempted']
    assert len(calls) == 1


def test_same_google_redirect_has_at_most_one_alternate_hop():
    calls = []
    r = resolver(lambda request: (calls.append(request) or httpx.Response(302, headers={'location': '/read/' + ID})))
    assert r.resolve(ITEM)['error_category'] == 'unexpected_google_redirect'
    assert len(calls) == 2


def test_missing_signature_does_not_guess_endpoint_or_retry():
    r = resolver(lambda _: httpx.Response(200, text='<html>Google News</html>'))
    assert r.resolve(ITEM)['error_category'] == 'signature_or_timestamp_missing'
    assert len(r.requests) == 1


def test_rpc_rate_limit_is_recorded_and_not_retried():
    r = resolver(lambda request: httpx.Response(200, text=PARAMS) if request.method == 'GET' else httpx.Response(429, headers={'retry-after': '120'}))
    assert r.resolve(ITEM)['error_category'] == 'google_http_429'
    assert r.requests[-1]['retry_after'] == '120'
    assert not r.resolve(ITEM)['resolution_attempted']
    assert len(r.requests) == 2


def test_google_challenge_page_stops_without_a_post():
    r = resolver(lambda _: httpx.Response(200, text='<html><title>Sorry - unusual traffic</title></html>'))
    assert r.resolve(ITEM)['error_category'] == 'google_challenge_or_consent'
    assert not r.resolve(ITEM)['resolution_attempted']
    assert len(r.requests) == 1


@pytest.mark.parametrize('url', ['https://publisher.example/', 'https://publisher.example/news', 'https://publisher.example/en/search/water', 'https://evil.example/news/egypt-expands-water-reuse-capacity', 'https://news.google.com/rss/articles/another', 'https://publisher.example.evil.example/news/a-long-article-slug', 'https://user:pass@publisher.example/news/a-long-article-slug'])
def test_homepage_categories_wrappers_and_wrong_hosts_are_rejected(url):
    assert not b.publisher_url(url, ITEM['expected_domain'])
    r = resolver(lambda request: httpx.Response(200, text=PARAMS if request.method == 'GET' else rpc(url)))
    assert r.resolve(ITEM)['error_category'] == 'invalid_or_wrong_publisher_url'


def test_length_framed_rpc_and_ambiguity_validation():
    frame = json.dumps([['wrb.fr', 'Fbv4je', json.dumps(['garturlres', DIRECT]), None, '0']])
    assert b.parse_rpc(")]}'\n\n" + str(len(frame)) + '\n' + frame) == DIRECT
    assert b.parse_signature(PARAMS) == ('signature-value', '1792420000')
    with pytest.raises(ValueError):
        b.parse_rpc(json.dumps([['wrb.fr', 'Fbv4je', json.dumps(['garturlres', DIRECT])]] * 2))
    with pytest.raises(ValueError):
        b.parse_rpc('[ ["wrb.fr", "unrelated", "[]"] ]')


def test_invalid_google_url_never_reaches_network():
    r = resolver(lambda _: pytest.fail('must not request invalid URL'))
    assert r.resolve(dict(ITEM, url='https://news.google.com.evil.example/rss/articles/' + ID))['error_category'] == 'invalid_google_wrapper'


def test_request_spacing_uses_injected_clock_and_sleep():
    now, waits = [0.0], []

    def wait(delay):
        waits.append(delay)
        now[0] += delay
    r = b.GoogleResolver(httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=PARAMS if request.method=='GET' else rpc()))), interval=2, sleep=wait, clock=lambda:now[0])
    assert r.resolve(ITEM)['resolution_success']
    assert waits == [2.0]


def test_oversized_google_response_fails_once_without_protocol_retry():
    r = resolver(lambda _: httpx.Response(200, text='x'*(b.MAX_BYTES+1)))
    assert r.resolve(ITEM)['error_category'] == 'google_response_too_large'
    assert len(r.requests) == 1


def test_actual_existing_retriever_and_body_sanity():
    prose = '<p>' + ('The new reuse plant supplies agricultural producers with treated water and expands water security capacity. ' * 5) + '</p>'
    page = f'<html><head><title>{TITLE}</title></head><body><article><h1>{TITLE}</h1>{prose*3}</article></body></html>'
    row = b.retrieve_publisher(ITEM, DIRECT, transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, text=page)))
    assert row['raw_status'] == 'extracted' and row['supported']
    assert not b.confirmed_wrong_story(row)
    assert row['canonical_url'] == DIRECT and row['request_count'] == 1


def test_paywall_metadata_preserves_retriever_raw_result_but_never_counts_recovery():
    page = f'<html><head><title>{TITLE}</title><script type="application/ld+json">{{"isAccessibleForFree":false}}</script></head><body><article><h1>{TITLE}</h1>' + '<p>Partial teaser and subscription text. ' * 40 + '</p></article></body></html>'
    row = b.retrieve_publisher(ITEM, DIRECT, transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, text=page)))
    assert not row['supported'] and row['publisher_access_failure'] == 'publisher_paywall_metadata'


def test_wrong_story_body_is_not_counted_as_incremental_recovery():
    page = '<html><head><title>Sports results around the world</title></head><body><article><h1>Sports results around the world</h1>' + '<p>The football team won its league and celebrated with spectators. </p>' * 25 + '</article></body></html>'
    row = b.retrieve_publisher(ITEM, DIRECT, transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={'content-type': 'text/html'}, text=page)))
    assert row['raw_status'] == 'extracted' and not row['supported']
    assert b.confirmed_wrong_story(row)


def test_unrelated_publisher_redirect_never_follows_external_host():
    calls = []
    row = b.retrieve_publisher(ITEM, DIRECT, transport=httpx.MockTransport(lambda request: (calls.append(request) or httpx.Response(302, headers={'location': 'https://other.example/news/another-news-story'}))))
    assert row['raw_status'] == 'fetch_failed'
    assert len(calls) == 1

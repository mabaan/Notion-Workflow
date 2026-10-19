"""Offline contracts for the isolated retrieval-only benchmark."""
import gzip
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import httpx
import pytest

from scripts import evaluate_scrapling_retrieval as bench
from research_automation.pipeline import article_retrieval as production

ITEM = {"title": "Egypt commissions solar storage facility", "url": "https://publisher.example/news/egypt-solar-storage", "publisher": "Publisher"}
PARAGRAPH = "Egypt commissioned a solar storage facility with new battery capacity and a grid connection. " * 5
BODY = PARAGRAPH * 3
HTML = f"<html><head><title>{ITEM['title']}</title><link rel='canonical' href='/news/egypt-solar-storage'></head><body><article><h1>{ITEM['title']}</h1>" + "".join(f"<p>{PARAGRAPH}</p>" for _ in range(3)) + "</article></body></html>"


def test_bounds_match_current_production_and_public_urls_are_required():
    for name in ("MAX_RESPONSE_BYTES", "MAX_TEXT_CHARS", "MINIMUM_TEXT_CHARS"):
        assert getattr(bench, name) == getattr(production, name)
    assert bench.public_url(ITEM["url"])
    assert not bench.public_url("file:///secret")
    assert not bench.public_url("http://127.0.0.1/article")
    assert not bench.public_url("https://user:password@publisher.example/article")
    assert bench.tokens("المياه والزراعة")


def test_actual_baseline_and_decoded_capture_accept_article_without_extra_fetch():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/html", "content-encoding": "gzip"}, content=gzip.compress(HTML.encode()))

    result = bench.baseline(ITEM, httpx.MockTransport(respond))
    assert len(requests) == 1
    assert result["status"] == "extracted"
    assert result["title_match"] == 1
    assert result["characters"] >= 300
    assert result["canonical_resolution_success"]
    assert requests[0].headers["user-agent"] == "SOMA-MATER-Research/1.0"


@pytest.mark.parametrize("status", sorted(bench.REFUSED))
def test_baseline_retains_publisher_access_refusal(status):
    result = bench.baseline(ITEM, httpx.MockTransport(lambda _: httpx.Response(status, text=HTML)))
    assert result["status"] == "blocked"
    assert result["characters"] == 0
    assert result["http_status"] == status


@pytest.mark.parametrize("url,title,text,reason", [
    ("https://publisher.example/", ITEM["title"], BODY, "landing"),
    (ITEM["url"], "All the latest world news", BODY, "title"),
    (ITEM["url"], ITEM["title"], "We use cookies. Manage privacy preferences. " * 40, "title"),
    (ITEM["url"], "404 not found", BODY, "title"),
    ("https://news.google.com/rss/articles/token", ITEM["title"], BODY, "wrapper"),
])
def test_long_non_article_text_is_not_success(url, title, text, reason):
    markup = HTML.replace(ITEM["title"], title)
    result = bench.assess(ITEM, "baseline", "extracted", markup, text, url, url, 200, .1)
    assert result["status"] == "wrong_page"
    assert reason in result["reason"]


@pytest.mark.parametrize("marker", [
    '<title>Just a moment</title>',
    '<script type="application/ld+json">{"isAccessibleForFree":false}</script>',
    '<p>Sign in to continue reading</p>',
])
def test_access_challenges_and_paywalls_are_not_success(marker):
    markup = HTML.replace("<head>", "<head>" + marker) if "<title>" in marker else HTML.replace("</body>", marker + "</body>")
    result = bench.assess(ITEM, "scrapling_static", "extracted", markup, BODY, ITEM["url"], ITEM["url"], 200, .1)
    assert result["status"] == "blocked"


def test_only_empty_public_javascript_shell_qualifies_for_rendering():
    shell = f"<html><head><title>{ITEM['title']}</title></head><body><div id='root'></div><script src='/app.js'></script><noscript>Enable JavaScript</noscript></body></html>"
    assert bench.page_signals(shell, ITEM["title"], ITEM["url"])["js_required"]
    assert not bench.page_signals(HTML + "<script src='/app.js'></script>", ITEM["title"], ITEM["url"])["js_required"]
    assert not bench.page_signals(shell, ITEM["title"], "https://news.google.com/rss/articles/id")["js_required"]
    first = dict(status="insufficient_content")
    second = dict(status="insufficient_content", js_required=True)
    assert bench.should_render(ITEM, first, second)
    assert not bench.should_render(ITEM, dict(status="blocked"), second)
    assert not bench.should_render(ITEM, dict(status="extracted"), second)
    assert not bench.should_render(ITEM, first, dict(status="blocked", js_required=True))


def test_canonical_urls_cannot_point_offsite_or_to_non_http_schemes():
    assert bench.canonical_url(ITEM["url"], ITEM["url"], HTML) == ITEM["url"]
    assert bench.canonical_url(ITEM["url"], ITEM["url"], HTML.replace("href='/news/egypt-solar-storage'", "href='https://unrelated.example/'")) == ITEM["url"]
    assert bench.canonical_url(ITEM["url"], ITEM["url"], HTML.replace("href='/news/egypt-solar-storage'", "href='javascript:alert(1)'")) == ITEM["url"]


def test_refusal_does_not_escalate_and_live_results_prevent_accidental_refetch(monkeypatch, tmp_path):
    calls = []

    def worker(item, method, python):
        calls.append(method)
        return dict(method=method, attempted=True, status="blocked", characters=0, latency_seconds=.1)

    monkeypatch.setattr(bench, "run_worker", worker)
    dataset = {"articles": [ITEM]}
    bench.run(dataset, tmp_path, Path("unused"), allow_rendered=True)
    assert calls == ["baseline"]
    with pytest.raises(ValueError, match="already exist"):
        bench.run(dataset, tmp_path, Path("unused"))
    assert calls == ["baseline"]


def test_metrics_separate_attempts_successes_and_skips():
    success = dict(attempted=True, status="extracted", characters=800, latency_seconds=.2, canonical_resolution_success=True)
    blocked = dict(attempted=True, status="blocked", characters=0, latency_seconds=.4)
    skipped = bench.skipped("scrapling_rendered", "not_attempted", "not needed")
    rows = [dict(publisher="P", results={"baseline": success, "scrapling_rendered": skipped}),
            dict(publisher="P", results={"baseline": blocked, "scrapling_rendered": skipped})]
    all_rows = [r for r in bench.summarize(rows) if r["publisher"] == "ALL"]
    baseline = next(r for r in all_rows if r["method"] == "baseline")
    assert (baseline["urls"], baseline["attempted"], baseline["successful"]) == (2, 2, 1)
    assert baseline["median_characters"] == 800
    assert baseline["canonical_resolved"] == 1
    assert next(r for r in all_rows if r["method"] == "scrapling_rendered")["attempted"] == 0


def test_installed_scrapling_selector_and_fetch_arguments_offline(tmp_path):
    python = bench.OUT / ".venv/Scripts/python.exe"
    if not python.exists():
        pytest.skip("Optional isolated Scrapling benchmark environment is not installed")
    source = tmp_path / "fixture.json"
    source.write_text(json.dumps(dict(item=ITEM, html=HTML, body=BODY)), encoding="utf-8")
    # Exercise the installed parser/API with a fake HTTP function: no live fetch.
    code = """
from pathlib import Path
import json,sys
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'src')]
from scripts import evaluate_scrapling_retrieval as b
from scrapling.fetchers import Fetcher
f=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert 'solar storage facility' in b.extract_scrapling(f['html'],f['item']['url'])
assert len(b.extract_scrapling(f['html']*20,f['item']['url'])) <= 12000
hero='<div class="article-content-hero"><h1>'+('Egypt solar storage headline '*30)+'</h1></div>'
assert b.extract_scrapling(hero+f['html'],f['item']['url']) == b.extract_scrapling(f['html'],f['item']['url'])
calls=[]
def fetch(url,**kw):
    calls.append(kw)
    kw['content_callback'](f['html'].encode())
    from types import SimpleNamespace
    return SimpleNamespace(status=200,headers={'content-type':'text/html'})
r=b.scrapling_static(f['item'],fetch)
assert r['status']=='extracted',r
assert len(calls)==1
assert calls[0]['impersonate'] is None and calls[0]['stealthy_headers'] is False
assert calls[0]['retries']==1 and calls[0]['follow_redirects'] is False
# Exercise the actual Fetcher argument forwarding without making HTTP requests.
import inspect
from curl_cffi.requests import Session, Response, Headers
original=Session.request
def no_network(self,method,**kwargs):
    inspect.signature(original).bind(self,method,**kwargs)
    kwargs['content_callback'](f['html'].encode())
    response=Response()
    response.url=kwargs['url']; response.status_code=200
    response.headers=Headers({'content-type':'text/html'})
    response.content=b''
    return response
Session.request=no_network
r=b.scrapling_static(f['item'])
assert r['status']=='extracted',r
def oversized(url,**kwargs):
    assert kwargs['content_callback'](b'x'*(b.MAX_RESPONSE_BYTES+1))==0
    raise RuntimeError('bounded callback aborted')
assert b.scrapling_static(f['item'],oversized)['status']=='too_large'
print('installed API and parser passed offline')
"""
    result = subprocess.run([str(python), "-c", code, str(source)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr + result.stdout

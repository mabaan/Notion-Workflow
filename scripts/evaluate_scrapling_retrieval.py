"""One-off public-article retrieval benchmark. Network requires --live/--worker.

No ingestion, discovery, Notion or LLM clients. Scrapling is imported only by its
isolated worker. Renderer uses ordinary Playwright + Scrapling parsing because
Scrapling 0.5 removed DynamicFetcher and its remaining browser API is stealth-based.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time
from urllib.parse import urljoin, urlsplit

import httpx
from lxml import html as lhtml

from research_automation.models.article import Article
from research_automation.utils.text import normalize_whitespace
from research_automation.utils.urls import clean_url, hostname_matches, is_google_news_url

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".preview/evaluations/scrapling_retrieval_20261019"
HEADERS = {"User-Agent": "SOMA-MATER-Research/1.0", "Accept": "text/html,application/xhtml+xml"}
METHODS = ("baseline", "scrapling_static", "scrapling_rendered")
REFUSED = {401, 402, 403, 407, 429, 451}
# Access refusals observed during source-URL lookup; never retry via another tool.
REFUSED_HOSTS = {"agbi.com", "zawya.com"}
STOP = set("the a an and of for to in on with by as is at from new says news".split())
# Match the current production bounds without importing readability into the
# incompatible Scrapling environment. A unit test checks these values.
MAX_RESPONSE_BYTES, MAX_TEXT_CHARS, MINIMUM_TEXT_CHARS = 2_000_000, 12_000, 300


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tokens(value):
    return {t for t in re.findall(r"[^\W_]+", value.casefold()) if len(t) > 2 and t not in STOP}


def forbidden(url):
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    return host in REFUSED_HOSTS


def public_url(url):
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and bool(parts.hostname) and not parts.username and not (
        parts.hostname in {"localhost", "127.0.0.1", "::1"} or re.match(r"^(10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)", parts.hostname)
    )


def page_signals(markup, expected_title, final_url):
    """Conservative sanity cues, not a claim of factual verification."""
    try:
        tree = lhtml.fromstring(markup or "<html></html>")
    except Exception:
        return {"page_title": "", "title_match": 0.0, "paragraphs": 0, "blocked_reason": "", "js_required": False, "article_structure": False}
    titles = tree.xpath("//h1//text()|//title/text()|//meta[@property='og:title']/@content")
    title = normalize_whitespace(" ".join(titles))
    expected = tokens(re.split(r"\s+(?:-|\|)\s+", expected_title)[0])
    match = len(expected & tokens(title)) / max(1, len(expected))
    visible = normalize_whitespace(" ".join(tree.xpath("//body//text()[not(ancestor::script or ancestor::style)]")))
    blocked = ""
    if re.search(r"access denied|just a moment|verify (?:you are|you're) human|captcha|robot check|security verification", title, re.I):
        blocked = "access challenge/error heading"
    elif re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', markup, re.I):
        blocked = "explicit paywall metadata"
    elif re.search(r"subscribe to (?:continue|read (?:this|the full) article)|sign in to (?:continue reading|read (?:this|the full) article)", visible, re.I):
        blocked = "explicit subscription/login requirement"
    paragraphs = sum(len(normalize_whitespace(p.text_content())) >= 60 for p in tree.xpath("//p"))
    article = bool(tree.xpath("//article|//*[@itemprop='articleBody']|//meta[@property='og:type' and @content='article']"))
    scripts = bool(tree.xpath("//script[@src]"))
    shell = bool(tree.xpath("//*[@id='root' or @id='app' or @id='__next'][not(normalize-space())]"))
    explicit_js = bool(re.search(r"(?:enable|requires?) javascript", visible, re.I))
    # A framework script by itself does not establish rendering necessity.
    needs_js = not blocked and not is_google_news_url(final_url) and paragraphs < 2 and scripts and (explicit_js or shell) and match >= .45
    return dict(page_title=title[:350], title_match=round(match, 3), paragraphs=paragraphs,
                blocked_reason=blocked, js_required=bool(needs_js), article_structure=article)


def assess(item, method, raw_status, markup, text, final_url, canonical, http_status, elapsed, **extra):
    signals = page_signals(markup, item["title"], final_url)
    text = normalize_whitespace(text)[:MAX_TEXT_CHARS]
    status, reason = raw_status, ""
    if http_status in REFUSED or signals["blocked_reason"]:
        status, reason = "blocked", signals["blocked_reason"] or f"HTTP {http_status}"
    elif raw_status == "extracted":
        path = urlsplit(canonical or final_url).path.strip("/")
        body_overlap = len(tokens(item["title"]) & tokens(text))
        if is_google_news_url(final_url):
            status, reason = "wrong_page", "unresolved Google News wrapper, not a publisher article"
        elif not path or path in {"news", "en", "articles", "search", "business", "world"}:
            status, reason = "wrong_page", "landing/category/search canonical URL"
        elif signals["title_match"] < .45 or body_overlap < 2:
            status, reason = "wrong_page", "expected title/subject not supported by extracted page"
        elif signals["paragraphs"] < 2 and not signals["article_structure"]:
            status, reason = "wrong_page", "no plausible article prose/structure"
        elif re.search(r"page not found|404 not found|something went wrong", signals["page_title"], re.I):
            status, reason = "wrong_page", "error page"
        elif len(text) < MINIMUM_TEXT_CHARS:
            status = "insufficient_content"
    # A wrapper with short text remains insufficient, with its cause made explicit.
    if status == "insufficient_content" and is_google_news_url(final_url):
        reason = "unresolved Google News wrapper"
    canonical_path = urlsplit(canonical).path.strip("/") if canonical else ""
    resolved = bool(canonical and not is_google_news_url(canonical) and canonical_path
                    and canonical_path not in {"news", "en", "articles", "search", "business", "world"}
                    and signals["title_match"] >= .45 and status != "wrong_page")
    return dict(method=method, attempted=True, status=status, raw_status=raw_status,
                reason=reason, final_url=final_url, canonical_url=canonical,
                canonical_resolution_success=resolved, http_status=http_status,
                characters=len(text), text_sha256=hashlib.sha256(text.encode()).hexdigest() if text else None,
                latency_seconds=round(elapsed, 3), **signals, **extra)


class CaptureTransport(httpx.BaseTransport):
    """Observe the unmodified baseline's bounded streamed response."""
    def __init__(self, transport=None):
        self.transport = transport or httpx.HTTPTransport(retries=0)
        self.body = bytearray()
        self.status = None
        self.final_url = ""
        self.policy_blocked = False
        self.network_requests = 0

    def handle_request(self, request):
        self.body.clear()
        self.final_url = str(request.url)
        if not public_url(str(request.url)) or forbidden(str(request.url)):
            self.status = None
            self.policy_blocked = True
            return httpx.Response(403, request=request)
        self.network_requests += 1
        response = self.transport.handle_request(request)
        self.status = response.status_code
        return response

    def close(self):
        self.transport.close()


class CaptureClient(httpx.Client):
    @contextmanager
    def stream(self, *args, **kwargs):
        with super().stream(*args, **kwargs) as response:
            original = response.iter_bytes
            capture = self._transport

            def decoded_bytes(*args, **kwargs):
                for chunk in original(*args, **kwargs):
                    if len(capture.body) < MAX_RESPONSE_BYTES:
                        capture.body.extend(chunk[:MAX_RESPONSE_BYTES - len(capture.body)])
                    yield chunk

            response.iter_bytes = decoded_bytes
            yield response


def baseline(item, transport=None):
    from research_automation.pipeline.article_retrieval import ArticleRetriever
    start = time.monotonic()
    capture = CaptureTransport(transport)
    article = Article(item["title"], item["url"], item["url"], item["publisher"], "")
    timeout = httpx.Timeout(connect=5, read=15, write=10, pool=5)
    with CaptureClient(transport=capture, follow_redirects=True, timeout=timeout, max_redirects=5, trust_env=False) as client:
        result = ArticleRetriever(client=client).retrieve(article)
    outcome = assess(item, "baseline", result.evidence_retrieval_status,
                  capture.body.decode("utf-8", "replace"), result.article_text,
                  capture.final_url or item["url"], result.canonical_url, capture.status,
                  time.monotonic() - start, url_resolution_status=result.url_resolution_status,
                  network_requests=capture.network_requests)
    if capture.policy_blocked:
        outcome.update(reason="observed publisher access policy; no request sent to restricted host", policy_blocked=True)
        outcome["attempted"] = bool(capture.network_requests)
    return outcome


def extract_scrapling(markup, url):
    from scrapling import Selector
    page = Selector(content=markup, url=url)
    # No adaptive storage, spider, site-wide links, or full-page text fallback.
    for selector in ("[itemprop='articleBody']", "[class*='article-body']", "[class*='article-content']", "[class*='story-body']", ".entry-content", "article", "main", "[role='main']"):
        candidates = []
        for node in page.css(selector)[:5]:
            prose = sum(len(normalize_whitespace(str(p.get_all_text(separator=" ", strip=True))))
                        for p in node.xpath(".//p[not(ancestor::nav or ancestor::aside or ancestor::footer)]"))
            if prose < MINIMUM_TEXT_CHARS:
                continue  # A long heading/hero/teaser alone is not an article body.
            text = str(node.get_all_text(separator=" ", strip=True, ignore_tags=(
                "script", "style", "noscript", "nav", "header", "footer", "aside", "form", "button",
            )))
            candidates.append(normalize_whitespace(text))
        if candidates and len(max(candidates, key=len)) >= MINIMUM_TEXT_CHARS:
            return max(candidates, key=len)[:MAX_TEXT_CHARS]
    paragraphs = page.xpath("//p[not(ancestor::nav or ancestor::header or ancestor::footer or ancestor::aside or ancestor::form)]")
    text = " ".join(str(p.get_all_text(separator=" ", strip=True)) for p in paragraphs[:100])
    return normalize_whitespace(text)[:MAX_TEXT_CHARS]


def canonical_url(original, final, markup):
    try:
        tree = lhtml.fromstring(markup)
        values = tree.xpath("//link[contains(concat(' ',normalize-space(@rel),' '),' canonical ')]/@href")
        candidate = clean_url(urljoin(final, values[0])) if values else ""
        if public_url(candidate) and not is_google_news_url(candidate) and hostname_matches(urlsplit(candidate).hostname or "", urlsplit(final).hostname or ""):
            return candidate
    except Exception:
        pass
    return clean_url(final or original)


def scrapling_static(item, fetch=None):
    from scrapling.fetchers import Fetcher
    start = time.monotonic()
    body = bytearray()
    too_large = False

    def receive(chunk):
        nonlocal too_large
        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
            too_large = True
            return 0
        body.extend(chunk)
        return len(chunk)

    current, response = item["url"], None
    try:
        for _ in range(6):
            if forbidden(current) or not public_url(current):
                return skipped("scrapling_static", "blocked", "access-policy restricted URL")
            body.clear()
            response = (fetch or Fetcher.get)(
                current, impersonate=None, stealthy_headers=False, headers=HEADERS,
                retries=1, timeout=20, follow_redirects=False, max_redirects=0,
                content_callback=receive,
            )
            if response.status in {301, 302, 303, 307, 308}:
                target = response.headers.get("location") or response.headers.get("Location")
                if target:
                    current = clean_url(urljoin(current, target))
                    continue
            break
        else:
            raise ValueError("redirect limit")
        markup = body.decode("utf-8", "replace")
        status = response.status
        content_type = str(response.headers.get("content-type", "")).lower()
        if status in REFUSED:
            raw = "blocked"
        elif status >= 400:
            raw = "fetch_failed"
        elif content_type and "html" not in content_type:
            raw = "unsupported_content"
        else:
            raw = "extracted"
        if page_signals(markup, item["title"], current)["blocked_reason"]:
            raw = "blocked"
        canonical = canonical_url(item["url"], current, markup)
        text = extract_scrapling(markup, current) if raw == "extracted" else ""
        if raw == "extracted" and len(text) < MINIMUM_TEXT_CHARS:
            raw = "insufficient_content"
        return assess(item, "scrapling_static", raw, markup, text, current, canonical, status, time.monotonic() - start)
    except Exception as exc:
        configuration = isinstance(exc, (TypeError, ModuleNotFoundError))
        return dict(method="scrapling_static", attempted=not configuration,
                    status="configuration_error" if configuration else "too_large" if too_large else "fetch_failed", reason=type(exc).__name__,
                    characters=0, latency_seconds=round(time.monotonic() - start, 3), js_required=False)


def skipped(method, status, reason):
    return dict(method=method, attempted=False, status=status, reason=reason,
                characters=0, latency_seconds=None, canonical_resolution_success=False, js_required=False)


def should_render(item, first, second):
    return (not is_google_news_url(item["url"]) and not forbidden(item["url"])
            and first["status"] in {"insufficient_content", "fetch_failed", "wrong_page"}
            and second["status"] in {"insufficient_content", "fetch_failed", "wrong_page"}
            and bool(second.get("js_required")) and not first.get("blocked_reason")
            and not second.get("blocked_reason"))


def rendered(item):
    # Plain browser, no Patchright/StealthyFetcher, fingerprint changes, login,
    # CAPTCHA automation, consent clicks, search referrer, proxies or stored state.
    from playwright.sync_api import sync_playwright
    start = time.monotonic()
    transferred = 0
    request_count = 0
    blocked = False
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"], service_workers="block")

        def route_request(route):
            nonlocal transferred, request_count, blocked
            request = route.request
            request_count += 1
            if blocked or request_count > 40 or request.method != "GET" or forbidden(request.url) or not public_url(request.url) or request.resource_type in {"image", "media", "font", "websocket"}:
                route.abort()
                return
            # Bound every permitted browser response and aggregate network bytes.
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
                with client.stream("GET", request.url, headers=HEADERS) as response:
                    if response.status_code in REFUSED:
                        blocked = True
                        route.fulfill(status=response.status_code, body=b"")
                        return
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        transferred += len(chunk)
                        if len(chunks) + len(chunk) > MAX_RESPONSE_BYTES or transferred > 5 * MAX_RESPONSE_BYTES:
                            route.abort()
                            return
                        chunks.extend(chunk)
                    route.fulfill(status=response.status_code, headers={k:v for k,v in response.headers.items() if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}}, body=bytes(chunks))

        context.route("**/*", route_request)
        page = context.new_page()
        page.set_default_timeout(20_000)
        response = page.goto(item["url"], wait_until="domcontentloaded", timeout=20_000)
        if response and response.status in REFUSED:
            blocked = True
        if not blocked:
            page.wait_for_timeout(1500)
        markup, final_url = page.content(), page.url
        status = response.status if response else None
        context.close()
        browser.close()
    if len(markup.encode("utf-8")) > MAX_RESPONSE_BYTES:
        return dict(method="scrapling_rendered", attempted=True, status="too_large", characters=0,
                    latency_seconds=round(time.monotonic() - start, 3))
    canonical = canonical_url(item["url"], final_url, markup)
    text = "" if blocked else extract_scrapling(markup, final_url)
    raw = "blocked" if blocked else "extracted" if len(text) >= MINIMUM_TEXT_CHARS else "insufficient_content"
    return assess(item, "scrapling_rendered", raw, markup, text, final_url, canonical, status, time.monotonic() - start,
                  renderer="ordinary Playwright + Scrapling Selector", network_bytes=transferred)


def run_worker(item, method, python):
    start = time.monotonic()
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    environment = {k:v for k,v in os.environ.items() if k.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}}
    environment["PYTHONPATH"] = str(ROOT / "src")
    process = subprocess.Popen([str(python), "-X", "utf8", str(Path(__file__).resolve()), "--worker", method],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", creationflags=flags,
                               env=environment)
    try:
        stdout, stderr = process.communicate(json.dumps(item), timeout=35)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, creationflags=flags)
        else:
            process.kill()
        process.communicate()
        return dict(method=method, attempted=True, status="fetch_failed", reason="35-second worker deadline", characters=0,
                    latency_seconds=round(time.monotonic()-start, 3))
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
        result["worker_wall_seconds"] = round(time.monotonic() - start, 3)
        return result
    except (ValueError, IndexError):
        return dict(method=method, attempted=True, status="fetch_failed", reason="worker failed (see environment/dependencies)",
                    characters=0, latency_seconds=round(time.monotonic()-start, 3))


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        for method, result in row["results"].items():
            groups[("ALL", method)].append(result)
            groups[(row["publisher"], method)].append(result)
    summaries = []
    for (publisher, method), results in sorted(groups.items()):
        attempted = [r for r in results if r["attempted"]]
        successes = [r for r in attempted if r["status"] == "extracted"]
        statuses = Counter(r["status"] for r in results)
        latencies = [r["latency_seconds"] for r in attempted if r.get("latency_seconds") is not None]
        summaries.append(dict(publisher=publisher, method=method, urls=len(results), attempted=len(attempted),
                              successful=len(successes), statuses=dict(statuses),
                              canonical_resolved=sum(bool(r.get("canonical_resolution_success")) for r in attempted),
                              median_characters=statistics.median([r["characters"] for r in successes]) if successes else 0,
                              median_attempted_characters=statistics.median([r["characters"] for r in attempted]) if attempted else 0,
                              median_latency=round(statistics.median(latencies), 3) if latencies else None))
    return summaries


def run(dataset, output, scrapling_python, allow_rendered=False):
    path = output / "results.jsonl"
    if path.exists():
        raise ValueError("Results already exist; choose a new output to prevent accidental refetching")
    rows, rendered_attempts = [], 0
    for index, item in enumerate(dataset["articles"], 1):
        first = run_worker(item, "baseline", sys.executable)
        if first["status"] == "blocked":
            second = skipped("scrapling_static", "blocked", "baseline access refusal; no alternate-client escalation")
        else:
            second = run_worker(item, "scrapling_static", scrapling_python)
        if second["status"] == "configuration_error":
            raise RuntimeError("Static worker configuration failed; do not count this as a publisher failure")
        if allow_rendered and rendered_attempts < 8 and should_render(item, first, second):
            third = run_worker(item, "scrapling_rendered", scrapling_python)
            rendered_attempts += 1
        else:
            third = skipped("scrapling_rendered", "not_attempted", "not an eligible public JavaScript shell, access restricted, disabled, or render cap reached")
        result = dict(item, results=dict(zip(METHODS, (first, second, third))))
        result["fallback_used"] = "none" if first["status"] == "extracted" else next((m for m,r in result["results"].items() if r["status"] == "extracted"), "snippet_only")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        rows.append(result)
        print(f"{index}/{len(dataset['articles'])}: {first['status']} / {second['status']} / {third['status']} - {item['publisher']}", flush=True)
    write(output / "metrics.json", summarize(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=OUT / "dataset.json")
    parser.add_argument("--output", type=Path, default=OUT / "run")
    parser.add_argument("--scrapling-python", type=Path, default=OUT / ".venv/Scripts/python.exe")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-rendered", action="store_true")
    parser.add_argument("--worker", choices=METHODS)
    args = parser.parse_args()
    if args.worker:
        item = json.load(sys.stdin)
        if not public_url(item["url"]):
            raise ValueError("An individual public HTTP(S) URL is required")
        try:
            result = {"baseline": baseline, "scrapling_static": scrapling_static, "scrapling_rendered": rendered}[args.worker](item)
        except Exception as exc:
            result = dict(method=args.worker, attempted=True, status="fetch_failed", reason=type(exc).__name__, characters=0, latency_seconds=0)
        print(json.dumps(result))
        return
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".preview/evaluations").resolve()):
        raise ValueError("Benchmark output must stay under .preview/evaluations")
    if args.live:
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        if not 1 <= len(dataset["articles"]) <= 50:
            raise ValueError("Benchmark must contain 1-50 fixed URLs")
        output.mkdir(parents=True, exist_ok=True)
        run(dataset, output, args.scrapling_python, args.allow_rendered)
    else:
        rows = [json.loads(line) for line in (output / "results.jsonl").read_text(encoding="utf-8").splitlines()]
        write(output / "metrics.json", summarize(rows))


if __name__ == "__main__":
    main()

# Google News URL resolution — 19 October 2026

**GO for a controlled URL-resolution implementation proposal. Production remains unchanged.**

Tested the actual **42 enriched Google News wrappers** from the latest shadow audit. **42/42 resolved to plausible article URLs on the expected publisher domains**. The unchanged ArticleRetriever returned **22 raw extractions**, of which **20 pass conservative body/headline/access checks**, compared with **0 extracted / 42 insufficient_content in the saved wrapper baseline. This is **20 incremental supported article bodies (47.6% of the target set)**.

Resolution used **84 Google requests**, median **3.5s per wrapper**, sequentially with at least two seconds between Google request starts. There were **0 Google HTTP 429 responses**; global Google stop reason: **none**. Publisher retrieval used **39 HTTP requests for 31 article attempts**, including redirects. Model/API cost: **$0**.

## Dataset and baseline

- Input: .preview/ingestion_audits/20261019T150812322754Z_6399d0a4.json. Only enrichment_attempted=true and discovery_method=google_news_rss records; all 42 original URLs were present. No random feed entries, invented snippets or new ingestion. Frozen dataset includes audit hash, expected titles/publishers, existing allocation rank and baseline status.
- Maximum 48 wrappers; actual 42, no truncation. Per-publisher round-robin tests existing enrichment priorities before later candidates.
- Baseline wrapper outcomes are reused from that exact read-only shadow audit, not refetched concurrently. All 42 recorded insufficient_content. This avoids additional Google requests; the time gap is a limitation. No Luna/Sol judgment is used as ground truth for URL/body correctness.

## Reviewed mechanism and boundaries

Pinned review: [SSujitX/google-news-url-decoder, 990bf393f0c0](https://github.com/SSujitX/google-news-url-decoder/tree/990bf393f0c0717988c6456c641a2c6af252b599), committed 2026-10-18T20:59:34Z. Its [protocol implementation](https://github.com/SSujitX/google-news-url-decoder/blob/990bf393f0c0717988c6456c641a2c6af252b599/googlenewsdecoder/_parse.py) extracts a per-article signature/timestamp from the RSS page and sends garturlreq through Fbv4je at the unofficial DotsSplashUi batchexecute endpoint. The current repository also supports batching many signatures into one POST; this benchmark uses one article per POST to avoid response-order ambiguity and to stop immediately on refusal.

- Start with /rss/articles/{id}?hl=en-US&gl=US&ceid=US:en, preserving any input locale. Opaque IDs are not treated as base64 publisher URLs. Only a same-ID, same-Google-host article redirect is allowed as one alternate hop; none was needed in this snapshot.
- Transparent SOMA-MATER-Research/1.0 User-Agent; existing httpx/lxml only; trust_env=False; no proxies, accounts, CAPTCHA handling, browser, impersonation, evasion, or paid decoder API. The upstream package was not installed. Upstream source/license copies are retained under reference/.
- Concurrency one, 15-second Google timeout, decoded response ceiling 2 MB, zero network retries. Any Google refusal/429/challenge/consent stops all remaining Google requests. Remaining inputs are explicitly marked unattempted. Publisher refusal/access requirements stop further publisher requests for that domain while Google resolution can continue.
- Validate decoded scheme, exact expected publisher/subdomain, and a plausible non-homepage/article path. Reject Google URLs, unrelated hosts, homepage/category/search/login/assets and ambiguous RPC payloads. Single-item RPC responses cannot be assigned by array position to a different input.

## Publisher breakdown

| Publisher | Wrappers | Resolved | Publisher attempts | Raw extracted | Supported bodies | Skipped after refusal | Median resolution s |
|---|---:|---:|---:|---:|---:|---:|---:|
| AGBI | 6 | 6 | 1 | 0 | 0 | 5 | 3.0705 |
| Arab News | 3 | 3 | 3 | 3 | 3 | 0 | 4.0 |
| Gulf News | 4 | 4 | 4 | 4 | 2 | 0 | 3.5625 |
| Khaleej Times | 3 | 3 | 3 | 3 | 3 | 0 | 3.359 |
| Nature | 6 | 6 | 6 | 0 | 0 | 0 | 3.1565000000000003 |
| Reuters | 7 | 7 | 1 | 0 | 0 | 6 | 3.547 |
| S&P Global | 1 | 1 | 1 | 0 | 0 | 0 | 3.579 |
| Saudi Gazette | 4 | 4 | 4 | 4 | 4 | 0 | 3.9924999999999997 |
| The National | 4 | 4 | 4 | 4 | 4 | 0 | 3.2655 |
| ZAWYA | 4 | 4 | 4 | 4 | 4 | 0 | 2.5235 |

## Failures, validation and limits

- URL-resolution failure categories: none. All returned URLs matched the expected publisher and passed article-path checks. Story validation: {'url_slug_supports_headline': 12, 'page_heading_matches': 22, 'story_not_independently_verified': 8}. No readable page showed an unrelated headline; access-restricted/opaque cases are not all independently verified.
- Raw publisher statuses: {'fetch_failed': 7, 'extracted': 22, 'blocked': 2}. Access failures: {'publisher_http_refusal': 3}. HTTP 405 is a refusal in this benchmark even though the existing retriever reports fetch_failed; HTTP 403 remains blocked. No alternate publisher fetcher or login was attempted.
- AGBI, Reuters and S&P each refused the first publisher request. Eleven remaining resolved URLs from those domains were deliberately not fetched. They are not counted as article-body failures or recoveries; their publisher/story bodies remain unverified.
- **Nature limitation:** 6 initial publisher redirects were stopped by this benchmark's strict article-path/host redirect guard. The original run did not retain the rejected redirect destinations. These fetch_failed records are a harness-policy limitation, not evidence that the default retriever inherently cannot read those Nature articles. They were not retried or counted as recovered. Nature support requires a later public-cookie/redirect review without authentication or bypass.
- The two additional Gulf News raw extractions have exact matching page headings but their extracted later sections do not pass the conservative headline-term check. They are plausible partial article evidence, not independently confirmed complete recoveries. Count 20 as the conservative supported minimum and 22 as raw extraction, not a claim of complete article text.
- Supported recovery requires the existing retriever to return extracted, at least two substantial HTML paragraphs, expected-heading and extracted-body keyword overlap, an article canonical, and no access gate. Cached headings/paragraph counts and text hashes are retained. Public page HTML is stored locally for audit; the report does not reproduce article bodies.
- Non-free metadata/login/challenge checks are conservative, including any isAccessibleForFree=false signal; related-item metadata can cause false negatives. No such paywall signal was needed to classify this run's three observed HTTP refusals.
- Unofficial, undocumented Google protocol: one successful sample cannot establish long-term stability. No second pass was made merely to inflate consistency evidence. Source markup/RPC formats/rate limits may change; a future implementation needs a bounded failure path that retains the original wrapper and existing metadata.

## Recommendation

**GO** is supported by the measured resolution reliability, correct publisher/article paths, no observed wrong readable stories, material body recovery, reasonable two-request resolution volume/latency, and no Google refusal or bypass. The report renderer uses practical benchmark checks (at least 90% resolutions, at least 25% supported incremental bodies, median resolution at most 15 seconds, no Google refusal) to make this recommendation explicit; these are evaluation checks, not changes to any production selection threshold.

Recommend the next narrowly scoped implementation review of URL resolution before the existing ArticleRetriever, with transparent networking, refusal stopping, original-wrapper retention and acquisition audit. This benchmark does not integrate or enable it. DIRECT_SITE_DISCOVERY_ENABLED remains false by default and its implementation is retained unchanged. Publisher blocks remain blocks; this is not unrestricted publisher access.

## Inspectable examples

Wrappers are shortened here; exact URLs and IDs remain in dataset.json/article_results.csv. These are actual decoded URLs, not publisher links reconstructed from titles.

- Arab News: Zelensky says Trump waiving sanctions ‘rewards’ Putin, warns Moscow wants ‘blackout’ in Ukraine - Arab News
  - `https://news.google.com/rss/articles/CBMi0wFBVV95cUxQT2V0…` → https://www.arabnews.com/world/zelensky-says-trump-waiving-sanctions-rewards-putin-warns-moscow-wants-blackout-in-ukraine-3006837-3006839 → `extracted` / `supported_extraction`.
- Gulf News: No more taxis or shuttle buses needed: Dubai's Etihad Rail station now directly linked to Metro - Gulf News
  - `https://news.google.com/rss/articles/CBMiqwFBVV95cUxQQU4x…` → https://gulfnews.com/living-in-uae/transport/dubai-etihad-rail-metro-pedestrian-bridge-now-open-1.500711688 → `extracted` / `supported_extraction`.
- Khaleej Times: Poultry farm using feed created by Sharjah Ruler gets UAE's first free-range label - Khaleej Times
  - `https://news.google.com/rss/articles/CBMiiAFBVV95cUxNY3Fp…` → https://www.khaleejtimes.com/uae/sharjah-fili-poultry-farm-first-free-range-label → `extracted` / `supported_extraction`.
- Saudi Gazette: Aramco to launch up to seven gas facilities by 2027, targets 80% sales growth by 2030 - Saudi Gazette
  - `https://news.google.com/rss/articles/CBMiVEFVX3lxTE1rRVlj…` → https://saudigazette.com.sa/article/665379 → `extracted` / `supported_extraction`.
- AGBI: Islamic Development Bank to mobilise $750m for food security - Arabian Gulf Business Insight | AGBI
  - `https://news.google.com/rss/articles/CBMiowFBVV95cUxOelhC…` → https://www.agbi.com/agriculture/2026/10/islamic-development-bank-to-mobilise-750m-for-food-security/ → `fetch_failed` / `publisher_http_refusal`.

## Files and verification

- New code only: scripts/evaluate_google_news_resolution.py and tests/test_google_news_resolution.py. All other additions are benchmark artifacts under this output directory. No production source/configuration, feed, prompt, schema, Notion, ingestion state, model/budget or dependency changes.
- dataset.json, results.json, article_results.json/CSV, summary.json, publisher_summary.json, google_responses/, publisher_pages/, reference/ and integrity/test verification retain the inputs, request ledger, raw outcomes and limits.
- Full pytest / git diff --check results: see verification.json and pytest.txt. Protected pre-existing file hashes: integrity.json.

Offline report replay: `.venv\Scripts\python.exe -X utf8 scripts/evaluate_google_news_resolution.py --report`.
Live stages refuse to overwrite results. Repeating the benchmark requires a new --out directory and a newly prepared dataset; no automatic retry or repeat was performed.

Final checks: **698 passed in 7.59s**, including 26 new offline cases; git diff --check exit 0. Protected pre-existing files: 129; changed: 0. Direct-site supplement effective flag was verified false.

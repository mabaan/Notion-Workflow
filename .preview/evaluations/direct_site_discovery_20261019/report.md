# Direct publisher discovery benchmark — 19 October 2026

**Decision: do not replace production feeds yet.** Direct URLs materially improve retrieval for four of five matched Google-wrapper comparisons, but no source demonstrates all of reliable recent discovery, manageable contamination, comparable useful coverage and improved existing-retriever results in this single snapshot.

Found **338 unique candidate URLs across 10 publishers**, of which **181 have recent dates** (114 exact/relative timestamps; 67 day-level dates). Another 8 fall on the uncertain 72-hour boundary. All retained URLs are same-publisher HTTP(S); none is a Google wrapper. These are discovery candidates, not mission-qualified articles.

Used **35/36 actual article HTTP requests**, including redirects and matched Google controls: 18 direct article attempts and five wrapper attempts. Direct raw results: 14 extracted, three insufficient_content, one too_large, zero blocked/fetch_failed. Independent access/body checks qualify only **12/18** as supported extraction; Nature and ZAWYA have explicit paywall/non-free metadata despite raw extracted status. The five wrappers all returned insufficient_content.

**No production files, dependencies, configuration, ingestion state or Notion records changed. No LLM or paid API calls; estimated paid API cost $0.** Source Registry was queried read-only for its actual Source URL and configured Feed URL. Reuters/S&P were not requested. No browser, stealth, impersonation, proxy, CAPTCHA handling or authentication was used.

## Method and reproducibility

- Source configuration frozen in `sources.json`; listing fetches started 2026-10-19 14:25:22 UTC (18:25 Dubai), feeds collected immediately afterwards. Exact per-source times, hashes and final URLs are retained.
- The first request always uses the registry Source URL. Scrapling 0.5 static fetches run in the existing isolated benchmark environment with transparent research User-Agent, impersonate=None, stealthy_headers=False, one attempt, 20-second timeout, 2 MB decoded-body ceiling and at most five same-publisher redirects. Three independent source requests may run concurrently. No additional listing pages crawled.
- Generic lxml DOM inspection of the saved static response selects article-shaped headline URLs, rejects navigation/login/author/category/tag/search/assets/media-only/job/event/collection paths, and requires a usable headline. Up to 100 candidate anchor occurrences are considered after cheap prechecks, retaining at most 50 unique URLs per source. At most 86 were considered in this snapshot. Counts are bounded samples, not exhaustive source inventories.
- A card cannot borrow a date/snippet from an ancestor containing another distinct story. Publication dates come from time/microdata, explicit relative labels or URL-matched embedded article JSON; site-level WebPage dates and modification times are ignored. National/Guardian literal dated URL paths are separately labeled day precision. Unknown or unzoned dates stay unknown.
- Primary recent window is the preceding 72 hours relative to each fetch. Day-only October 17–19 dates count as recent; October 16 day-only dates are boundary-uncertain and excluded from the primary count. Literal path dates indicate apparent recency, not independently verified publication timestamps. Relative dates use actual UTC fetch time; snippets are never invented.
- Configured Google News queries are used unchanged; Guardian uses its existing native world RSS. All feed entries are frozen, not truncated to match a homepage. Google descriptions that contain only title + publisher do not count as useful snippets. Google indexing dates may differ from publisher publication dates.
- Overlap uses exact normalized headlines (Unicode, case, punctuation and publisher suffix). It can miss rewritten titles, labels and live-blog headline changes. Nature/CFR queries are topic/region-filtered, unlike homepages; Guardian international homepage differs from world RSS. Raw counts alone do not measure mission recall.
- Downstream uses the unchanged production ArticleRetriever: two direct URLs per available publisher, preferring recent headline matches, plus one same-headline Google control where available. Unknown-date examples are used only when no dated candidate exists (Fast Company). Round-robin source order limits budget bias. Redirects count toward the hard shared 36-request limit; access refusals/paywall signals stop further requests for that publisher. Maximum direct attempts per publisher was two, below the requested three.
- Canonicals and raw extraction statuses are preserved verbatim. Separate audit checks examine heading overlap, article prose and access metadata. No body parser changes or Scrapling body extraction are involved.
- Benchmark-only markup exceptions: ZAWYA `date-utc` milliseconds; Arc/Fusion JSON assignments parsed as JSON without executing script (no usable ordinary-article dates recovered for National). Gulf News JSON uses generic explicit URL/publication-date keys. No publisher exceptions were added to production.
- The existing isolated Scrapling environment is reused because its cssselect requirement conflicts with production readability-lxml. No packages installed or project dependency changes. Environment details are in `environment.json`.

## Discovery counts

All counts below are within the saved bounded snapshot. D = direct listing, F = configured feed; F is native RSS for Guardian. D recent includes day precision; boundary-uncertain and unknown dates are excluded. R/S = usable descriptions/snippets.

| Publisher | Fetch | D links | D dates | D R/S | D recent | F recent | D/F direct URLs | F wrappers | D/F seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AGBI | fetch_failed | 0 | 0 | 0 | 0 | 11 | 0/0 | 100 | 0.059/1.771 |
| Arab News | fetched | 50 | 34 | 0 | 34 | 50 | 50/0 | 100 | 0.392/1.768 |
| Council on Foreign Relations | fetched | 42 | 42 | 11 | 6 | 2 | 42/0 | 100 | 0.839/1.768 |
| Fast Company Middle East | fetched | 20 | 0 | 0 | 0 | 1 | 20/0 | 100 | 0.582/1.694 |
| Gulf News | fetched | 23 | 23 | 23 | 21 | 29 | 23/0 | 100 | 0.129/1.682 |
| Khaleej Times | fetched | 25 | 12 | 0 | 12 | 42 | 25/0 | 100 | 0.11/1.124 |
| Nature | fetched | 25 | 24 | 13 | 5 | 2 | 25/0 | 100 | 1.459/1.62 |
| Reuters | excluded_prior_refusal | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | not tested |
| S&P Global | excluded_prior_refusal | 0 | 0 | 0 | 0 | 0 | 0/0 | 0 | not tested |
| Saudi Gazette | fetched | 41 | 38 | 1 | 17 | 20 | 41/0 | 100 | 0.788/1.472 |
| Saudi Press Agency | fetched | 0 | 0 | 0 | 0 | 42 | 0/0 | 100 | 0.571/0.961 |
| Smart Water Magazine | blocked | 0 | 0 | 0 | 0 | 0 | 0/0 | 100 | 0.107/1.599 |
| The Guardian International | fetched | 50 | 50 | 0 | 49 | 38 | 50/45 | 0 | 0.087/0.251 |
| The National | fetched | 50 | 50 | 0 | 36 | 28 | 50/0 | 100 | 0.262/1.121 |
| ZAWYA | fetched | 12 | 1 | 1 | 1 | 83 | 12/0 | 100 | 0.608/0.96 |

AGBI was HTTP 405; Smart Water HTTP 429; SPA was HTTP 200 with no anchors. Reuters/S&P zeros mean excluded, not empty feeds. Timing is network fetch plus metadata parsing, excluding interpreter startup; no retries. All 338 direct candidates have usable titles. All 1,245 feed entries have dates; 1,243 have titles ≥20 characters; only Guardian supplies usable feed snippets (45/45). Full title/date/snippet counts are in comparison.csv.

## Recent overlap and freshness gaps

| Publisher | Shared | Direct only | Feed only | All-date shared | Recent feed matching undated direct | D duplicate anchors | D unknown dates | Boundary dates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AGBI | 0 | 0 | 11 | 0 | 0 | 0 | 0 | 0 |
| Arab News | 8 | 26 | 42 | 12 | 3 | 36 | 16 | 0 |
| Council on Foreign Relations | 2 | 4 | 0 | 3 | 0 | 15 | 0 | 0 |
| Fast Company Middle East | 0 | 0 | 1 | 2 | 1 | 7 | 20 | 0 |
| Gulf News | 0 | 21 | 29 | 0 | 0 | 0 | 0 | 0 |
| Khaleej Times | 2 | 10 | 40 | 4 | 2 | 20 | 13 | 0 |
| Nature | 0 | 5 | 2 | 2 | 0 | 1 | 1 | 3 |
| Reuters | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| S&P Global | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Saudi Gazette | 1 | 16 | 19 | 1 | 0 | 7 | 3 | 0 |
| Saudi Press Agency | 0 | 0 | 42 | 0 | 0 | 0 | 0 | 0 |
| Smart Water Magazine | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| The Guardian International | 6 | 43 | 32 | 6 | 0 | 4 | 0 | 1 |
| The National | 2 | 34 | 26 | 2 | 0 | 6 | 0 | 4 |
| ZAWYA | 0 | 1 | 83 | 0 | 0 | 1 | 11 | 0 |

Duplicate anchors count repeated usable-headline links within the considered sample; image-only links are rejected separately. No duplicate URL remains in the accepted output. Feed URL duplicates were zero. `story_overlap.csv` names every primary-window shared/unique story and its direct/feed URLs. `direct_candidates.csv` and `feed_candidates.csv` retain all accepted metadata, including unknown dates and older articles.

## Article-link quality audit

Reviewed eight evenly spaced accepted title/URL/card positions per publisher (80 total), with the saved card excerpts in link_review.json/CSV. These are a structural audit, not a claim that 80 full article bodies were fetched. No obvious navigation/category link remains in this sample. Two are uncertain: a CFR book/report presentation and a Gulf News branded visual feature. Two additional records are clearly sponsored article-shaped pages (Fast Company and National).

**Observed definite non-article rate: 0/80. Uncertain/potential false positives: 2/80 (2.5%). Sponsored content: 2/80 (2.5%), reported separately.** This small structured sample is not a statistical population estimate; unreviewed candidates may contain other false positives. Article discovery is not editorial qualification. The prototype initially exposed Nature job ads, CFR event pages, collection pages and cartoons; generic URL-type exclusions removed those before the frozen final output. No headline-specific blacklist was added.

| Publisher | Reviewed | Obvious navigation/category false positives | Uncertain | Sponsored |
|---|---:|---:|---:|---:|
| AGBI | 0 | not tested | 0 | 0 |
| Arab News | 8 | 0 | 0 | 0 |
| Council on Foreign Relations | 8 | 0 | 1 | 0 |
| Fast Company Middle East | 8 | 0 | 0 | 1 |
| Gulf News | 8 | 0 | 1 | 0 |
| Khaleej Times | 8 | 0 | 0 | 0 |
| Nature | 8 | 0 | 0 | 0 |
| Reuters | 0 | not tested | 0 | 0 |
| S&P Global | 0 | not tested | 0 | 0 |
| Saudi Gazette | 8 | 0 | 0 | 0 |
| Saudi Press Agency | 0 | not tested | 0 | 0 |
| Smart Water Magazine | 0 | not tested | 0 | 0 |
| The Guardian International | 8 | 0 | 0 | 0 |
| The National | 8 | 0 | 0 | 1 |
| ZAWYA | 8 | 0 | 0 | 0 |

## Existing retriever results

| Publisher | Direct attempts | Raw extracted | Supported extracted | Other direct outcomes | Matched wrapper |
|---|---:|---:|---:|---|---|
| AGBI | 0 | 0 | 0 | — | not tested |
| Arab News | 2 | 2 | 2 | — | insufficient_content |
| Council on Foreign Relations | 2 | 0 | 0 | {'insufficient_content': 2} | insufficient_content |
| Fast Company Middle East | 2 | 2 | 2 | — | not tested |
| Gulf News | 2 | 0 | 0 | {'too_large': 1, 'insufficient_content': 1} | not tested |
| Khaleej Times | 2 | 2 | 2 | — | insufficient_content |
| Nature | 1 | 1 | 0 | {'blocked_or_paywalled': 1} | not tested |
| Reuters | 0 | 0 | 0 | — | not tested |
| S&P Global | 0 | 0 | 0 | — | not tested |
| Saudi Gazette | 2 | 2 | 2 | — | insufficient_content |
| Saudi Press Agency | 0 | 0 | 0 | — | not tested |
| Smart Water Magazine | 0 | 0 | 0 | — | not tested |
| The Guardian International | 2 | 2 | 2 | — | not tested |
| The National | 2 | 2 | 2 | — | insufficient_content |
| ZAWYA | 1 | 1 | 0 | {'blocked_or_paywalled': 1} | not tested |

For the five matched stories, direct URLs succeeded for Arab News, Khaleej Times, Saudi Gazette and National (4/5); CFR failed with either URL (0/1). All five Google controls failed. Thus direct discovery solves the URL problem on some sources, but not CFR extraction, Gulf News size/extraction, or publisher access requirements. Fast Company direct examples are undated at discovery and unpaired. Guardian native feed already has direct URLs. This sample cannot estimate the full production success rate.

Canonical URLs, source URLs, per-attempt latency, request counts, raw/audited statuses, captured-page file paths and extracted-text hashes are preserved in retrieval.json and retrieval_results.csv. Full request ledger includes redirects. No additional article retrieval was performed after the 35-request run.

## Per-source recommendations

| Publisher | Recommendation | Reason |
|---|---|---|
| AGBI | KEEP_GOOGLE_NEWS_RSS | Transparent static GET returned 405; stopped. Earlier accessibility is not reproducible with this request profile. |
| Arab News | NEEDS_MORE_TESTING | 2/2 direct bodies worked; matched Google wrapper failed. But 34 dated recent links versus 50 feed stories, only 8 recent exact matches, and no listing snippets. Test coverage across repeated snapshots before replacing the feed. |
| Council on Foreign Relations | KEEP_GOOGLE_NEWS_RSS | Good listing dates and both recent feed headlines present, but 0/2 direct bodies extracted. Saved HTML contains prose; the existing retriever still fails, so direct discovery alone does not fix this source. |
| Fast Company Middle East | NEEDS_MORE_TESTING | 2/2 direct bodies worked, but all 20 listing candidates lack publication dates. One recent feed headline matches an undated direct candidate; this is not a proven recent listing. |
| Gulf News | NEEDS_MORE_TESTING | Strong embedded metadata: all 23 candidates have dates and snippets. But 0/2 direct bodies extracted (one too large, one insufficient); exact headline overlap is zero. Resolve extraction/coverage uncertainty in a separate task. |
| Khaleej Times | NEEDS_MORE_TESTING | 2/2 direct bodies worked versus a failed matched wrapper. Only 12 dated recent links versus 42 feed stories; 13 direct candidates remain undated. |
| Nature | KEEP_GOOGLE_NEWS_RSS | Five day-dated recent homepage items do not match the two recent mission-filtered feed headlines. The sampled article has explicit paywall metadata; no unqualified body recovery demonstrated. |
| Reuters | KEEP_GOOGLE_NEWS_RSS | Direct static unavailable from the prior explicit refusal. Excluded: zero direct-site or article requests in this benchmark. |
| S&P Global | KEEP_GOOGLE_NEWS_RSS | Direct static unavailable from the prior explicit refusal. Excluded: zero direct-site or article requests in this benchmark. |
| Saudi Gazette | NEEDS_MORE_TESTING | 2/2 direct bodies worked versus a failed matched wrapper. Recent counts are close (17 versus 20), but only one headline matches; the homepage also exposes many older features. Counts alone do not establish comparable coverage. |
| Saudi Press Agency | KEEP_GOOGLE_NEWS_RSS | Static 200 is an empty Next.js root with zero anchors. Embedded mainNews has seven English records and timestamps but no explicit article URLs. Validate a public route in a future experiment; no guessed URL or API was requested. |
| Smart Water Magazine | KEEP_GOOGLE_NEWS_RSS | Fresh transparent static GET returned 429; no retry. Current feed had no recent entries either. Preserve acquisition and reassess access/freshness later. |
| The Guardian International | KEEP_NATIVE_RSS | Existing world RSS already supplies direct URLs, real snippets and exact dates. Homepage and world feed have different section coverage; there is no Google-wrapper problem to fix. |
| The National | NEEDS_MORE_TESTING | 2/2 direct bodies worked versus a failed matched wrapper. Homepage redirects to /uae/ and all 50 dates come from literal URL paths, not listing publication timestamps. Only two recent headline matches; verify breadth and date reliability before replacement. |
| ZAWYA | KEEP_GOOGLE_NEWS_RSS | Only 1/12 direct candidates has a date versus 83 recent feed stories. The sampled article requires an account and has explicit non-free metadata; the retriever raw success is not accepted as full evidence. |

**USE_DIRECT_SITE_DISCOVERY recommendations: zero.** The most promising follow-up candidates are Arab News, Saudi Gazette, Khaleej Times and National because matched direct URLs improve extraction. A bounded repeated-listing/date/coverage validation is needed before replacement. This does not call for a pipeline redesign or new service.

## Saudi Press Agency

The configured English Source URL /en returned an empty div#__next and zero anchors, with Next.js script bundles and __NEXT_DATA__. The latter already contains seven English mainNews records with UUIDs, titles and publication timestamps. No explicit article URL is supplied. Runtime configuration keys do not expose a validated news API route. This is a rendered-link problem, not evidence that no static metadata exists. No alternate route, API endpoint or UUID-derived URL was guessed/fetched. Next step: inspect documented/public article-link construction and benchmark the supplied JSON records separately, before considering any browser. See spa_diagnostic.json.

## Sample titles and direct URLs

Two examples per successful publisher, using recent dated candidates first. Unknown-date examples are explicitly marked; links are for inspection, not editorial recommendations.

### Arab News

- [Saudi civil defense says 6 citizens injured after projectile falls in Najran](https://www.arabnews.com/saudi-arabia/saudi-civil-defense-says-6-citizens-injured-after-projectile-falls-in-najran-3007036) — 2026-10-18T15:56:27.617Z; listing_card.
- [Arab Views: Should Riyadh negotiate with Houthis?](https://www.arabnews.com/saudi-arabia/arab-views-should-riyadh-negotiate-with-houthis-3007116) — 2026-10-19T14:06:44.074Z; listing_card.

### Council on Foreign Relations

- [The Victory of Asymmetry in the Iran War](https://www.cfr.org/articles/the-victory-of-asymmetry-in-the-iran-war) — 2026-10-16T16:56:08.000Z; listing_card.
- [Ukraine’s Attacks on Russian Data Centers Lay Bare a Global Risk to AI](https://www.cfr.org/articles/ukraines-attacks-on-russian-data-centers-lay-bare-a-global-risk-to-ai) — 2026-10-16T21:31:50.000Z; listing_card.

### Fast Company Middle East

- [Can you be good at stuff you don’t like doing?](https://fastcompanyme.com/work-life/can-you-be-good-at-stuff-you-dont-like-doing) — unknown date; unknown.
- [Could weight-loss drugs reshape the food economy in the Middle East?](https://fastcompanyme.com/impact/could-weight-loss-drugs-reshape-the-food-economy-in-the-middle-east) — unknown date; unknown.

### Gulf News

- [Iran: US responsible for 'insecurity' in Hormuz strait](https://gulfnews.com/world/mena/middle-east-live-trump-backs-netanyahu-as-iran-issues-warning-saudi-houthi-strikes-escalate-1.500715444) — 1792378948168; embedded_article_json.
- [UAE President receives French President in Abu Dhabi](https://gulfnews.com/uae/government/uae-president-receives-french-president-upon-his-arrival-on-official-visit-to-the-uae-2-1.500716197) — 1792417879875; embedded_article_json.

### Khaleej Times

- [UAE President receives France’s Macron in Abu Dhabi during Gulf tour to strengthen ties](https://www.khaleejtimes.com/uae/uae-president-macron-abu-dhabi-gulf-tour-boost-ties) — 8m ago; listing_card.
- ['Most beautiful dream': Dubai Ruler pens letter of unity to Arabian Gulf people](https://www.khaleejtimes.com/uae/dubai-ruler-sheikh-mohammed-bin-rashid-al-maktoum-letter-gulf-unity) — 5h ago; listing_card.

### Nature

- [How pregnancy reshapes the brain throughout life](https://www.nature.com/articles/d41586-026-03312-8) — 2026-10-19; listing_card.
- [‘Fiercely stubborn’: the US scientists continuing their research amid funding cuts](https://www.nature.com/articles/d41586-026-03315-5) — 2026-10-19; listing_card.

### Saudi Gazette

- [GCC urges global designation of Houthis as terrorist group](https://saudigazette.com.sa/article/665530/saudi-arabia/gcc-urges-global-designation-of-houthis-as-terrorist-group) — 20 h ago; listing_card.
- [Saudi defense minister meets UAE president to discuss strengthening partnership](https://saudigazette.com.sa/article/665529/saudi-arabia/saudi-defense-minister-meets-uae-president-to-discuss-strengthening-partnership) — 21 h ago; listing_card.

### The Guardian International

- [French prime minister calls for ‘local and partial’ curfews after riots](https://www.theguardian.com/world/2026/oct/19/french-police-lost-control-during-riots-concedes-interior-minister) — 2026-10-19; literal_url_date.
- [Europe live French PM blames ‘ultra-left’ for exploiting protests as he seeks partial curfews](https://www.theguardian.com/world/live/2026/oct/19/europe-france-protests-riots-macron-ukraine-russia-zelenskyy-sweden-latest-news-updates) — 2026-10-19; literal_url_date.

### The National

- [Exclusive Inside flydubai Flight 1073: Hero captain tells of fight for his life](https://www.thenationalnews.com/news/uae/2026/10/19/smit-machchhar-interview-what-happened-inside-the-cockpit-of-flydubai-flight-1073) — 2026-10-19; literal_url_date.
- [Interview Sheikha Latifa on her 20 years of Asian Games success and new Olympic dream](https://www.thenationalnews.com/sport/2026/10/19/sheikha-latifa-on-her-20-years-of-asian-games-success-and-new-olympic-dream) — 2026-10-19; literal_url_date.

### ZAWYA

- [Dubai Investments to sell 20% in DIP Holding in first DFM IPO this year](https://www.zawya.com/en/capital-markets/dubai-investments-to-sell-20-in-dip-holding-in-first-dfm-ipo-this-year-1740327) — 1792391760899; listing_card.
- [More details on Dubai Investment Park IPO expected next week](https://www.zawya.com/en/capital-markets/investment/more-details-on-dubai-investment-park-ipo-expected-next-week-1717793) — unknown date; unknown.

## Checks and files

- New repository code: scripts/evaluate_direct_site_discovery.py and tests/test_direct_site_discovery.py only. The latter adds 34 offline cases.
- Full pytest: **636 passed in 6.07s**. git diff --check result recorded in verification.json.
- Protected pre-existing files: **124**, including two ingestion-state files; changed: **0**. Includes .env/configuration, production code, dependencies, previous scripts/tests and docs.
- Output includes sources.json, pages/, listing_fetches/, direct/, feeds/, comparison.json/CSV, candidate CSVs, story_overlap.csv, retrieval.json/CSV with canonical URLs, retrieval_pages/, link_review.json/CSV, spa_diagnostic.json, recommendations.json, environment.json, integrity.json and test verification.

Offline rerender/checks (no network):

```powershell
.venv\Scripts\python.exe -X utf8 scripts/evaluate_direct_site_discovery.py analyze
.venv\Scripts\python.exe -X utf8 scripts/evaluate_direct_site_discovery.py compare
.venv\Scripts\python.exe -X utf8 .preview/evaluations/direct_site_discovery_20261019/render_report.py
.venv\Scripts\python.exe -X utf8 -m pytest -q
git diff --check
```

For a new explicitly authorized live snapshot, use a NEW --out directory: snapshot with the project interpreter (read-only registry); fetch-listings with the reused isolated Scrapling interpreter; fetch-feeds, analyze, compare, retrieve, diagnose-spa and verify with the project interpreter. Live stages refuse to overwrite existing snapshots. The default output date is the requested benchmark date; every response records its real acquisition time.

## Limits

Single snapshot, homepage-only discovery and a small retrieval sample. Homepage/editorial curation and query scope differ from Google indexing; title edits can undercount overlap. Day-only path dates and relative labels are weaker than independently verified publication times. No semantic/event dedupe, classifier precision/recall, article relevance scores or ingestion throughput is claimed. No exhaustive article-body or factual verification. Rate limits, access responses and source markup may change. The prototype is intentionally independent of production.

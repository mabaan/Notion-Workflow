"""Render this frozen benchmark, with recorded editorial audit notes. No network."""
import csv
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts import evaluate_direct_site_discovery as b

OUT = Path(__file__).parent
rows = b.read(OUT / 'comparison.json')
retrieval = b.read(OUT / 'retrieval.json')
review = b.read(OUT / 'link_review.json')
verification = b.read(OUT / 'verification.json')
integrity = b.read(OUT / 'integrity.json')

DECISIONS = {
    'AGBI': ('KEEP_GOOGLE_NEWS_RSS', 'Transparent static GET returned 405; stopped. Earlier accessibility is not reproducible with this request profile.'),
    'Arab News': ('NEEDS_MORE_TESTING', '2/2 direct bodies worked; matched Google wrapper failed. But 34 dated recent links versus 50 feed stories, only 8 recent exact matches, and no listing snippets. Test coverage across repeated snapshots before replacing the feed.'),
    'Council on Foreign Relations': ('KEEP_GOOGLE_NEWS_RSS', 'Good listing dates and both recent feed headlines present, but 0/2 direct bodies extracted. Saved HTML contains prose; the existing retriever still fails, so direct discovery alone does not fix this source.'),
    'Fast Company Middle East': ('NEEDS_MORE_TESTING', '2/2 direct bodies worked, but all 20 listing candidates lack publication dates. One recent feed headline matches an undated direct candidate; this is not a proven recent listing.'),
    'Gulf News': ('NEEDS_MORE_TESTING', 'Strong embedded metadata: all 23 candidates have dates and snippets. But 0/2 direct bodies extracted (one too large, one insufficient); exact headline overlap is zero. Resolve extraction/coverage uncertainty in a separate task.'),
    'Khaleej Times': ('NEEDS_MORE_TESTING', '2/2 direct bodies worked versus a failed matched wrapper. Only 12 dated recent links versus 42 feed stories; 13 direct candidates remain undated.'),
    'Nature': ('KEEP_GOOGLE_NEWS_RSS', 'Five day-dated recent homepage items do not match the two recent mission-filtered feed headlines. The sampled article has explicit paywall metadata; no unqualified body recovery demonstrated.'),
    'Reuters': ('KEEP_GOOGLE_NEWS_RSS', 'Direct static unavailable from the prior explicit refusal. Excluded: zero direct-site or article requests in this benchmark.'),
    'S&P Global': ('KEEP_GOOGLE_NEWS_RSS', 'Direct static unavailable from the prior explicit refusal. Excluded: zero direct-site or article requests in this benchmark.'),
    'Saudi Gazette': ('NEEDS_MORE_TESTING', '2/2 direct bodies worked versus a failed matched wrapper. Recent counts are close (17 versus 20), but only one headline matches; the homepage also exposes many older features. Counts alone do not establish comparable coverage.'),
    'Saudi Press Agency': ('KEEP_GOOGLE_NEWS_RSS', 'Static 200 is an empty Next.js root with zero anchors. Embedded mainNews has seven English records and timestamps but no explicit article URLs. Validate a public route in a future experiment; no guessed URL or API was requested.'),
    'Smart Water Magazine': ('KEEP_GOOGLE_NEWS_RSS', 'Fresh transparent static GET returned 429; no retry. Current feed had no recent entries either. Preserve acquisition and reassess access/freshness later.'),
    'The Guardian International': ('KEEP_NATIVE_RSS', 'Existing world RSS already supplies direct URLs, real snippets and exact dates. Homepage and world feed have different section coverage; there is no Google-wrapper problem to fix.'),
    'The National': ('NEEDS_MORE_TESTING', '2/2 direct bodies worked versus a failed matched wrapper. Homepage redirects to /uae/ and all 50 dates come from literal URL paths, not listing publication timestamps. Only two recent headline matches; verify breadth and date reliability before replacement.'),
    'ZAWYA': ('KEEP_GOOGLE_NEWS_RSS', 'Only 1/12 direct candidates has a date versus 83 recent feed stories. The sampled article requires an account and has explicit non-free metadata; the retriever raw success is not accepted as full evidence.'),
}


def save_csv(name, data):
    if not data:
        return
    fields = list(dict.fromkeys(k for r in data for k in r))
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)


flat = []
all_direct, all_feed, overlap_records = [], [], []
for row in rows:
    record = {k: v for k, v in row.items() if not isinstance(v, (dict, list))}
    for method in ('direct', 'feed'):
        record.update({method + '_' + k: v for k, v in row[method].items() if not isinstance(v, dict)})
    flat.append(record)
    name = row['publisher']
    direct = b.read(OUT / 'direct' / (b.slug(name) + '.json'))['accepted']
    feed_path = OUT / 'feeds' / (b.slug(name) + '.json')
    feed = b.read(feed_path)['entries'] if feed_path.exists() else []
    all_direct.extend(direct)
    all_feed.extend(feed)
    a = {b.normalized_title(x['title'], name): x for x in direct if x['freshness'] in {'recent', 'recent_date_only'}}
    c = {b.normalized_title(x['title'], name): x for x in feed if x['freshness'] in {'recent', 'recent_date_only'}}
    for key in sorted(a.keys() | c.keys()):
        item = a.get(key) or c[key]
        overlap_records.append(dict(publisher=name, title=item['title'], membership='both' if key in a and key in c else ('direct_only' if key in a else 'feed_only'), direct_url=a[key]['url'] if key in a else '', feed_url=c[key]['url'] if key in c else ''))
save_csv('comparison.csv', flat)
save_csv('direct_candidates.csv', all_direct)
save_csv('feed_candidates.csv', all_feed)
save_csv('story_overlap.csv', overlap_records)
save_csv('retrieval_results.csv', retrieval['results'])
save_csv('link_review.csv', review)
b.write(OUT / 'recommendations.json', [{'publisher': name, 'recommendation': d[0], 'reason': d[1]} for name, d in DECISIONS.items()])

direct_results = [r for r in retrieval['results'] if r['method'] == 'direct']
paired = [r for r in retrieval['results'] if r['method'] == 'paired_google_wrapper']
counts = Counter(r['audited_status'] for r in direct_results)
recent = sum(r['direct']['recent'] for r in rows)
total = len(all_direct)
lines = [
    '# Direct publisher discovery benchmark — 19 October 2026', '',
    '**Decision: do not replace production feeds yet.** Direct URLs materially improve retrieval for four of five matched Google-wrapper comparisons, but no source demonstrates all of reliable recent discovery, manageable contamination, comparable useful coverage and improved existing-retriever results in this single snapshot.', '',
    f'Found **{total} unique candidate URLs across 10 publishers**, of which **{recent} have recent dates** (114 exact/relative timestamps; 67 day-level dates). Another 8 fall on the uncertain 72-hour boundary. All retained URLs are same-publisher HTTP(S); none is a Google wrapper. These are discovery candidates, not mission-qualified articles.', '',
    f'Used **{retrieval["network_requests"]}/36 actual article HTTP requests**, including redirects and matched Google controls: 18 direct article attempts and five wrapper attempts. Direct raw results: 14 extracted, three insufficient_content, one too_large, zero blocked/fetch_failed. Independent access/body checks qualify only **12/18** as supported extraction; Nature and ZAWYA have explicit paywall/non-free metadata despite raw extracted status. The five wrappers all returned insufficient_content.', '',
    '**No production files, dependencies, configuration, ingestion state or Notion records changed. No LLM or paid API calls; estimated paid API cost $0.** Source Registry was queried read-only for its actual Source URL and configured Feed URL. Reuters/S&P were not requested. No browser, stealth, impersonation, proxy, CAPTCHA handling or authentication was used.', '',
    '## Method and reproducibility', '',
    '- Source configuration frozen in `sources.json`; listing fetches started 2026-10-19 14:25:22 UTC (18:25 Dubai), feeds collected immediately afterwards. Exact per-source times, hashes and final URLs are retained.',
    '- The first request always uses the registry Source URL. Scrapling 0.5 static fetches run in the existing isolated benchmark environment with transparent research User-Agent, impersonate=None, stealthy_headers=False, one attempt, 20-second timeout, 2 MB decoded-body ceiling and at most five same-publisher redirects. Three independent source requests may run concurrently. No additional listing pages crawled.',
    '- Generic lxml DOM inspection of the saved static response selects article-shaped headline URLs, rejects navigation/login/author/category/tag/search/assets/media-only/job/event/collection paths, and requires a usable headline. Up to 100 candidate anchor occurrences are considered after cheap prechecks, retaining at most 50 unique URLs per source. At most 86 were considered in this snapshot. Counts are bounded samples, not exhaustive source inventories.',
    '- A card cannot borrow a date/snippet from an ancestor containing another distinct story. Publication dates come from time/microdata, explicit relative labels or URL-matched embedded article JSON; site-level WebPage dates and modification times are ignored. National/Guardian literal dated URL paths are separately labeled day precision. Unknown or unzoned dates stay unknown.',
    '- Primary recent window is the preceding 72 hours relative to each fetch. Day-only October 17–19 dates count as recent; October 16 day-only dates are boundary-uncertain and excluded from the primary count. Literal path dates indicate apparent recency, not independently verified publication timestamps. Relative dates use actual UTC fetch time; snippets are never invented.',
    '- Configured Google News queries are used unchanged; Guardian uses its existing native world RSS. All feed entries are frozen, not truncated to match a homepage. Google descriptions that contain only title + publisher do not count as useful snippets. Google indexing dates may differ from publisher publication dates.',
    '- Overlap uses exact normalized headlines (Unicode, case, punctuation and publisher suffix). It can miss rewritten titles, labels and live-blog headline changes. Nature/CFR queries are topic/region-filtered, unlike homepages; Guardian international homepage differs from world RSS. Raw counts alone do not measure mission recall.',
    '- Downstream uses the unchanged production ArticleRetriever: two direct URLs per available publisher, preferring recent headline matches, plus one same-headline Google control where available. Unknown-date examples are used only when no dated candidate exists (Fast Company). Round-robin source order limits budget bias. Redirects count toward the hard shared 36-request limit; access refusals/paywall signals stop further requests for that publisher. Maximum direct attempts per publisher was two, below the requested three.',
    '- Canonicals and raw extraction statuses are preserved verbatim. Separate audit checks examine heading overlap, article prose and access metadata. No body parser changes or Scrapling body extraction are involved.',
    '- Benchmark-only markup exceptions: ZAWYA `date-utc` milliseconds; Arc/Fusion JSON assignments parsed as JSON without executing script (no usable ordinary-article dates recovered for National). Gulf News JSON uses generic explicit URL/publication-date keys. No publisher exceptions were added to production.',
    '- The existing isolated Scrapling environment is reused because its cssselect requirement conflicts with production readability-lxml. No packages installed or project dependency changes. Environment details are in `environment.json`.', '',
    '## Discovery counts', '',
    'All counts below are within the saved bounded snapshot. D = direct listing, F = configured feed; F is native RSS for Guardian. D recent includes day precision; boundary-uncertain and unknown dates are excluded. R/S = usable descriptions/snippets.', '',
    '| Publisher | Fetch | D links | D dates | D R/S | D recent | F recent | D/F direct URLs | F wrappers | D/F seconds |',
    '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|',
]
for r in rows:
    d, f = r['direct'], r['feed']
    timing = f'{r["direct_latency_seconds"]}/{r["feed_latency_seconds"]}' if r['direct_latency_seconds'] is not None else 'not tested'
    lines.append(f'| {r["publisher"]} | {r["direct_fetch_status"]} | {d["total"]} | {d["dates"]} | {d["snippets"]} | {d["recent"]} | {f["recent"]} | {d["direct"]}/{f["direct"]} | {f["wrappers"]} | {timing} |')
lines += ['', f'AGBI was HTTP 405; Smart Water HTTP 429; SPA was HTTP 200 with no anchors. Reuters/S&P zeros mean excluded, not empty feeds. Timing is network fetch plus metadata parsing, excluding interpreter startup; no retries. All {total} direct candidates have usable titles. All {len(all_feed):,} feed entries have dates; {sum(r["feed"]["titles"] for r in rows):,} have titles ≥20 characters; only Guardian supplies usable feed snippets (45/45). Full title/date/snippet counts are in comparison.csv.', '',
          '## Recent overlap and freshness gaps', '',
          '| Publisher | Shared | Direct only | Feed only | All-date shared | Recent feed matching undated direct | D duplicate anchors | D unknown dates | Boundary dates |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:
    d = r['direct']
    lines.append(f'| {r["publisher"]} | {r["overlap"]} | {r["unique_direct"]} | {r["unique_feed"]} | {r["overlap_all_dates"]} | {r["recent_feed_matches_undated_direct"]} | {r["direct_duplicate_links"]} | {d["total"]-d["dates"]} | {d["boundary_uncertain"]} |')
lines += ['', 'Duplicate anchors count repeated usable-headline links within the considered sample; image-only links are rejected separately. No duplicate URL remains in the accepted output. Feed URL duplicates were zero. `story_overlap.csv` names every primary-window shared/unique story and its direct/feed URLs. `direct_candidates.csv` and `feed_candidates.csv` retain all accepted metadata, including unknown dates and older articles.', '',
          '## Article-link quality audit', '',
          'Reviewed eight evenly spaced accepted title/URL/card positions per publisher (80 total), with the saved card excerpts in link_review.json/CSV. These are a structural audit, not a claim that 80 full article bodies were fetched. No obvious navigation/category link remains in this sample. Two are uncertain: a CFR book/report presentation and a Gulf News branded visual feature. Two additional records are clearly sponsored article-shaped pages (Fast Company and National).', '',
          '**Observed definite non-article rate: 0/80. Uncertain/potential false positives: 2/80 (2.5%). Sponsored content: 2/80 (2.5%), reported separately.** This small structured sample is not a statistical population estimate; unreviewed candidates may contain other false positives. Article discovery is not editorial qualification. The prototype initially exposed Nature job ads, CFR event pages, collection pages and cartoons; generic URL-type exclusions removed those before the frozen final output. No headline-specific blacklist was added.', '',
          '| Publisher | Reviewed | Obvious navigation/category false positives | Uncertain | Sponsored |',
          '|---|---:|---:|---:|---:|']
for name in (r['publisher'] for r in rows):
    a = [x for x in review if x['publisher'] == name]
    lines.append(f'| {name} | {len(a)} | {0 if a else "not tested"} | {sum(x["review"].startswith("uncertain") for x in a)} | {sum(x["review"] == "sponsored_article_candidate" for x in a)} |')
lines += ['', '## Existing retriever results', '',
          '| Publisher | Direct attempts | Raw extracted | Supported extracted | Other direct outcomes | Matched wrapper |',
          '|---|---:|---:|---:|---|---|']
for name in (r['publisher'] for r in rows):
    a = [x for x in direct_results if x['publisher'] == name]
    other = Counter(x['audited_status'] for x in a if x['audited_status'] != 'extracted')
    p = [x for x in paired if x['publisher'] == name]
    lines.append(f'| {name} | {len(a)} | {sum(x["raw_status"]=="extracted" for x in a)} | {sum(x["audited_status"]=="extracted" for x in a)} | {dict(other) if other else "—"} | {p[0]["raw_status"] if p else "not tested"} |')
lines += ['', 'For the five matched stories, direct URLs succeeded for Arab News, Khaleej Times, Saudi Gazette and National (4/5); CFR failed with either URL (0/1). All five Google controls failed. Thus direct discovery solves the URL problem on some sources, but not CFR extraction, Gulf News size/extraction, or publisher access requirements. Fast Company direct examples are undated at discovery and unpaired. Guardian native feed already has direct URLs. This sample cannot estimate the full production success rate.', '',
          'Canonical URLs, source URLs, per-attempt latency, request counts, raw/audited statuses, captured-page file paths and extracted-text hashes are preserved in retrieval.json and retrieval_results.csv. Full request ledger includes redirects. No additional article retrieval was performed after the 35-request run.', '',
          '## Per-source recommendations', '',
          '| Publisher | Recommendation | Reason |', '|---|---|---|']
for name, (decision, reason) in DECISIONS.items():
    lines.append(f'| {name} | {decision} | {reason} |')
lines += ['', '**USE_DIRECT_SITE_DISCOVERY recommendations: zero.** The most promising follow-up candidates are Arab News, Saudi Gazette, Khaleej Times and National because matched direct URLs improve extraction. A bounded repeated-listing/date/coverage validation is needed before replacement. This does not call for a pipeline redesign or new service.', '',
          '## Saudi Press Agency', '',
          'The configured English Source URL /en returned an empty div#__next and zero anchors, with Next.js script bundles and __NEXT_DATA__. The latter already contains seven English mainNews records with UUIDs, titles and publication timestamps. No explicit article URL is supplied. Runtime configuration keys do not expose a validated news API route. This is a rendered-link problem, not evidence that no static metadata exists. No alternate route, API endpoint or UUID-derived URL was guessed/fetched. Next step: inspect documented/public article-link construction and benchmark the supplied JSON records separately, before considering any browser. See spa_diagnostic.json.', '',
          '## Sample titles and direct URLs', '',
          'Two examples per successful publisher, using recent dated candidates first. Unknown-date examples are explicitly marked; links are for inspection, not editorial recommendations.', '']
for row in rows:
    name = row['publisher']
    candidates = [x for x in all_direct if x['publisher'] == name]
    candidates.sort(key=lambda x: (x['freshness'] not in {'recent', 'recent_date_only'}, x['freshness'] == 'unknown'))
    if candidates:
        lines.append(f'### {name}')
        lines.append('')
        for x in candidates[:2]:
            lines.append(f'- [{x["title"]}]({x["url"]}) — {x["date_raw"] or "unknown date"}; {x["date_source"]}.')
        lines.append('')
lines += ['## Checks and files', '',
          f'- New repository code: scripts/evaluate_direct_site_discovery.py and tests/test_direct_site_discovery.py only. The latter adds 34 offline cases.',
          f'- Full pytest: **{verification["pytest_summary"]}**. git diff --check result recorded in verification.json.',
          f'- Protected pre-existing files: **{integrity["protected_files"]}**, including two ingestion-state files; changed: **{len(integrity["changed_preexisting_files"])}**. Includes .env/configuration, production code, dependencies, previous scripts/tests and docs.',
          '- Output includes sources.json, pages/, listing_fetches/, direct/, feeds/, comparison.json/CSV, candidate CSVs, story_overlap.csv, retrieval.json/CSV with canonical URLs, retrieval_pages/, link_review.json/CSV, spa_diagnostic.json, recommendations.json, environment.json, integrity.json and test verification.', '',
          'Offline rerender/checks (no network):', '', '```powershell',
          '.venv\Scripts\python.exe -X utf8 scripts/evaluate_direct_site_discovery.py analyze',
          '.venv\Scripts\python.exe -X utf8 scripts/evaluate_direct_site_discovery.py compare',
          '.venv\Scripts\python.exe -X utf8 .preview/evaluations/direct_site_discovery_20261019/render_report.py',
          '.venv\Scripts\python.exe -X utf8 -m pytest -q', 'git diff --check', '```', '',
          'For a new explicitly authorized live snapshot, use a NEW --out directory: snapshot with the project interpreter (read-only registry); fetch-listings with the reused isolated Scrapling interpreter; fetch-feeds, analyze, compare, retrieve, diagnose-spa and verify with the project interpreter. Live stages refuse to overwrite existing snapshots. The default output date is the requested benchmark date; every response records its real acquisition time.', '',
          '## Limits', '',
          'Single snapshot, homepage-only discovery and a small retrieval sample. Homepage/editorial curation and query scope differ from Google indexing; title edits can undercount overlap. Day-only path dates and relative labels are weaker than independently verified publication times. No semantic/event dedupe, classifier precision/recall, article relevance scores or ingestion throughput is claimed. No exhaustive article-body or factual verification. Rate limits, access responses and source markup may change. The prototype is intentionally independent of production.', '']
(OUT / 'report.md').write_text('\n'.join(lines), encoding='utf8')
print(OUT / 'report.md')

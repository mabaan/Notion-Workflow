` # Controlled Google News resolver integration

Implemented on 19 October 2026. The feature remains disabled in both default and
effective settings. No live HTTP requests, model calls, Notion writes, article
collection or persistent ingestion-state changes were performed during this task.
All earlier work in the checkout was preserved.

## Exact application, test and documentation files changed in this task

| File | Change |
|---|---|
| `.env.example` | Document default-off `GOOGLE_NEWS_URL_RESOLUTION_ENABLED`. |
| `README.md` | Link resolver operation documentation. |
| `src/research_automation/config.py` | Default-false boolean setting and environment loader. |
| `src/research_automation/models/article.py` | In-memory resolution audit dictionary; no Notion field. |
| `src/research_automation/pipeline/google_news_resolver.py` | New isolated decoder, validation, bounded requests, per-run cache and retrieval decorator. |
| `src/research_automation/pipeline/ingestion.py` | Default-off retrieval decoration and terminal metrics. |
| `src/research_automation/pipeline/candidate_ranking.py` | Record both resolved URL aliases after checking prior identity, including duplicate skips. |
| `src/research_automation/pipeline/luna_selection.py` | Same URL alias retention at Luna's existing retrieval point. |
| `src/research_automation/pipeline/candidate_audit.py` | Candidate diagnostics and unique-input resolution/evidence summary in JSON/Markdown. |
| `tests/test_google_news_resolver_integration.py` | 72 mocked/offline regression cases. |
| `docs/google_news_resolution.md` | Behavior, limits, metrics caveats, risks and exact shadow command. |

Artifacts created here: this report, `protected_before.json`, `integrity.json`,
`replay.py`, `replay_results.json`, and `verification.json`. The replay depends on
the existing saved benchmark responses; production code and ordinary tests do
not depend on those local files.

## Integration and identity

`run_ingestion` wraps its existing retrieval callback only when the flag is true
and a callback exists. The resolver is invoked from the existing allocated
detailed-enrichment retrieval point. Neither collection nor metadata
classification resolves URLs. Direct URLs and wrappers already resolved through
feed metadata proceed directly to the existing retriever.

`article.url` remains the feed URL. A validated publisher destination becomes
`canonical_url`. Existing identity refresh recomputes the URL hash; canonical
duplicates still skip enrichment and remain backfillable. Attempted URL tracking
retains wrapper and publisher aliases even when the canonical URL is already
processed. No change to same-event detection, scoring, coverage or selection.

## Failure, bounds and cache

Any decoding, destination-validation, refusal or unexpected resolver failure
records a compact reason and passes the original wrapper to ArticleRetriever.
The resolver cannot approve or silently discard an article. Retrieval failure
continues to the existing evidence-limited detailed assessment. No new LLM stage
or additional enrichment request is added.

Normal decoding uses one signature GET and one RPC POST. One same-identity Google
redirect is allowed: at most three requests per uncached attempt, 15-second HTTP
timeout each, 2 MB decoded response cap each, serial two-second request spacing,
transparent User-Agent, no proxy and no retries. Google refusals/challenges/429s
stop further decoder requests for the run. Existing wrapper fallback retrieval
is preserved and can still contact Google independently of this latch.

Actual decoding attempts are additionally capped by the existing enrichment
maximum (48 by default) so duplicate backfills cannot expand decoder work to the
whole collected pool. At default settings this is at most 144 decoder requests,
normally at most 96, plus existing publisher/wrapper retrieval. Exhaustion records
`resolution_attempt_budget_exhausted` and uses the normal wrapper path. The LLM
32/48/8 budgets remain unchanged.

The normalized-wrapper memory cache stores successes and failures for one run.
Cache hits generate no decoding requests and still work after the attempt cap.
Destinations are checked again against each candidate's registry publisher host.
No persistent cache, new dependency, proxy, browser or external service.

The existing ArticleRetriever was not modified. Its normal redirects, extraction,
feed content and blocked/access statuses remain intact. The benchmark article-path
redirect guard is not imported; no Nature special case or Scrapling fallback.

## Audits and evidence limits

Candidate audits preserve acquisition method, wrapper, expected/resolved hostname,
attempt/cache/status, request count, latency, failure category, real 429 count and
before/after evidence statuses. Signatures, Google payloads, bodies and raw
transport errors are not written to normal audits.

Summary metrics count unique input identities across phases. They distinguish
wrappers reaching retrieval from actual enrichment, attempts from cache/skips,
resolved/failed/rate-limited candidates from real HTTP 429s, and publisher blocked
outcomes from Google refusal. They include latency, request totals, cap skips,
evidence transitions and selected evidence breakdowns for all winners and the
resolved subset.

`publisher_bodies_recovered` is explicitly the existing raw `extracted` count.
`supported_article_bodies_recovered` is `null`, because completeness/support is
not independently measurable from the existing retrieval result. It must not be
interpreted as the earlier benchmark's more conservative supported-body count.
Likewise, the recorded pre-retrieval status is not a fresh control wrapper fetch;
no causal evidence uplift is claimed. Partial/paywall text and HTTP 405 retain
the existing retriever's semantics. These limitations are documented and printed
alongside enabled-run recovery metrics.

## Verification

- Full pytest: **770 passed in 6.48 seconds**, including 72 new resolver cases;
  the inherited baseline was 698 tests.
- `git diff --check`: exit 0. Git prints only its configured LF/CRLF advisory for
  `luna_selection.py`; no whitespace errors.
- Frozen benchmark replay: **42/42 resolved to the expected publisher domains**
  using **84 saved responses** through the production module and MockTransport.
  This was offline decoding, not fresh publisher retrieval or a paid shadow run.
- Protected-file integrity: 131 baseline files checked; only the eight intended
  existing files above changed. Actual `.env`, ingestion state, prompts,
  classifier, retrieval implementation, Source Registry/schema, feeds, discovery
  implementation and earlier benchmark/hybrid code remain unchanged.
- Effective flags: Google resolver false; direct-site discovery false. Effective
  batch size 100; enrichment 32/48/8; registered minimum relevance 4.

Coverage includes disabled legacy behavior, exact publisher handoff/provenance,
canonical hash and alias dedup, no pre-classification resolution, all metadata
batches finishing before retrieval, allocation limits, irrelevant/no-enrich
skips, malformed/Google/wrong-domain destinations, subdomains, normalized success
and failure caching, domain revalidation, timeouts/network/malformed RPC failures,
framed responses, bounded redirects, refusal/challenge/429 stopping, duplicate-
heavy pool caps, publisher blocked statuses and normal redirects, raw evidence
audits, configuration validation and no dry-run Notion/state writes.

## Exact next shadow command (not executed)

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:GOOGLE_NEWS_URL_RESOLUTION_ENABLED = "true"
$env:DIRECT_SITE_DISCOVERY_ENABLED = "false"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-sol"
.\.venv\Scripts\python.exe -X utf8 scripts\run_daily_ingestion_local.py --dry-run --all-sources --limit 12
```

The unofficial protocol can change or rate-limit. Domain metadata can be absent
or stale, and plausible-article path validation can reject unusual legitimate
URLs. Resolution does not verify article identity or full evidence. Publisher
access limits remain, and the next real shadow run must assess body quality and
actual latency under current network conditions. No default enablement is implied.

# Controlled Google News URL resolution

`GOOGLE_NEWS_URL_RESOLUTION_ENABLED=false` is the default in `Settings`, environment
loading and `.env.example`. The actual `.env` is unchanged.
`DIRECT_SITE_DISCOVERY_ENABLED` remains default-off and independent.

When enabled, `run_ingestion` decorates its existing retrieval callback with one
`GoogleNewsResolvingRetriever` and one in-memory resolver for the run. Both Luna
and legacy deterministic selection invoke it at their existing bounded retrieval
point, after classification/screening and allocation of a detailed-enrichment
opportunity. Collection, metadata classification and deferred/rejected candidates
never invoke the resolver. No retrieval callback, `--no-enrich`, no remaining
opportunity, or a non-Google effective URL means no decoding request.

The original feed `article.url` is retained. A validated destination becomes
`canonical_url`; existing identity refresh computes its URL hash and subsequent
canonical dedup can skip an already processed publisher URL before an LLM call.
Attempted URL tracking retains the wrapper and canonical aliases, including new
wrapper aliases rejected after resolution. Same-event detection is unchanged.
Canonical duplicates skipped before enrichment remain backfillable under the
existing budget behavior; resolution opportunities and actual LLM calls are
therefore reported separately.

## Protocol and bounds

The isolated resolver uses the signature/timestamp and `garturlreq` / `Fbv4je`
mechanism demonstrated by the saved benchmark. It adds no decoder dependency.
Protocol attribution and the MIT notice are included in the module.

- One attempt per normalized wrapper per run, no network retries.
- Actual decoding attempts are capped at the existing
  `ARTICLE_ENRICHMENT_MAX_BUDGET` (48 by default). Canonical duplicate backfills
  cannot expand this cap. Cache lookups still work after the cap; other candidates
  record `resolution_attempt_budget_exhausted` and use normal wrapper retrieval.
  No classifier or LLM enrichment budget is changed. At the default cap the
  decoder can make at most 144 requests (normally at most 96), independent of
  any existing wrapper/publisher retrieval requests.
- Normally one Google RSS article GET and one RPC POST. At most one same-host,
  same-article Google redirect is allowed, for a maximum of three requests.
  A valid direct publisher redirect can finish decoding in one request; the
  existing ArticleRetriever fetches the destination separately.
- Serial requests with at least two seconds between Google request starts.
- A 15-second HTTP timeout and 2 MB decoded response limit per Google request.
- Transparent `SOMA-MATER-Research/1.0` agent. No environment proxy, login,
  browser, challenge bypass, alternate endpoint probes or persistent cache.
- A Google 429, access refusal, challenge, consent redirect or RPC redirect stops
  further **decoding** requests for the run. Subsequent candidates still follow
  the original wrapper retrieval path. That existing path can itself contact
  Google; the decoder's refusal latch does not change ArticleRetriever behavior.

Results have compact status, original/resolved URL, request count, elapsed seconds,
failure category and attempt/cache/429 indicators. The normalized-wrapper cache
holds successes and failures for this run only. Cache hits incur zero additional
Google requests and are counted separately. Cached destinations are revalidated
against each candidate's expected publisher domain.

## Validation and safe fallback

Only public HTTP(S) destinations with a plausible article path are accepted.
Homepages, obvious category/search/login routes, Google destinations, credentials,
invalid ports/hosts, private IP literals, non-article assets and malformed results
are rejected. Expected publisher hosts come from the already loaded Source
Registry `Source URL`, keyed by source page ID. Existing hostname matching permits
publisher subdomains. When metadata is absent, only general URL validation is
possible; the audit records the expected hostname when available.

Any failure records a compact reason and passes the original wrapper to the
existing ArticleRetriever. It does not approve or discard the candidate and adds
no LLM call. Publisher fetching, extraction, feed-content handling, normal
redirects and access outcomes are unchanged. Raw blocked statuses remain blocked;
there is no Nature-specific path rule, benchmark redirect guard, Scrapling body
fallback or publisher-access workaround.

## Audit interpretation

Candidate JSON records original acquisition method and wrapper, expected/resolved
publisher hostname, attempt/status/cache information, request count, latency,
failure category, actual Google 429 count and evidence status before/after
retrieval. No signatures, internal RPC payloads, body text or transport exception
details are written to the audit.

JSON/Markdown and enabled-run console summaries count unique candidate identities
across phases, rather than phase observations. They report wrappers reaching
retrieval and actual enrichment, attempts, resolutions, failures, 429s, cache hits,
request totals, median attempted-resolution latency, publisher `blocked` outcomes,
evidence transitions and raw recovered extractions. Rate-limited candidates
include later skipped candidates; `google_429_responses` counts only real responses.
`failed` includes rate-limited outcomes. Selected evidence is broken out as
`publisher_extracted`, `feed_content` and `metadata_only`, both for all winners
and the resolved subset. The disabled flag does not add terminal output.

`publisher_bodies_recovered` means raw `extracted` results from the existing
retriever, not independently verified complete articles. The earlier benchmark
found partial bodies among raw extractions; this integration does not repeat its
separate HTML completeness checks or change production extraction. Therefore
`supported_article_bodies_recovered` is explicitly `null` (unmeasured), never an
invented support count. Likewise, the stored pre-retrieval status is not a new
control fetch: before/after transitions do not prove causal recovery or uplift.
Publisher refusals count the existing retriever's `blocked` category; other raw
failures and partial/paywall text retain existing semantics.

## Next controlled shadow run

This implementation was verified offline. No paid shadow run was executed.
The following command performs a real read-only ingestion with API calls, but no
Notion or persistent ingestion-state writes. It retains current batch/budget
settings (100 articles per classification batch; 32/48/8 enrichment defaults).

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:GOOGLE_NEWS_URL_RESOLUTION_ENABLED = "true"
$env:DIRECT_SITE_DISCOVERY_ENABLED = "false"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-sol"
.\.venv\Scripts\python.exe -X utf8 scripts\run_daily_ingestion_local.py --dry-run --all-sources --limit 12
```

Set `$env:GOOGLE_NEWS_URL_RESOLUTION_ENABLED = "false"` to restore the original
retrieval path. No other flag or budget override is required.

The unofficial protocol may change, rate limits can still occur, destination
path heuristics can reject unusual legitimate URLs, and missing/stale publisher
domain metadata weakens destination validation. Decoding does not establish
article identity, complete evidence, editorial suitability or permission to
access publisher content. Existing editorial gates and human review still apply.

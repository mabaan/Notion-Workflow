# Four-source direct discovery supplement (shadow only)

`DIRECT_SITE_DISCOVERY_ENABLED=false` is the default. Existing feed fetching,
candidate order, classifier calls and selection behavior remain unchanged when
disabled. Setting it to `true` requires `--dry-run`; a live run fails before any
Notion access, collection, model calls or writes. This is a supplement to the
existing feed pool, not a replacement feed or a second classifier stage.

## Collection and limits

Normal configured feeds run first, with their existing scheduling and networking.
For **due, active registered publishers only**, the supplement then fetches the
existing Source URL for Arab News, Saudi Gazette, Khaleej Times and The National.
Both the registry name and expected publisher domain must match. No other source
is enabled; native Guardian RSS and Reuters/S&P acquisition are unchanged.

Each publisher gets exactly one static HTTP GET, with no redirects, retries,
pagination or deeper listing fetches. A duplicate registry row cannot trigger a
second request. The response ceiling is 2 MB decoded HTML; connection/read/write/
pool timeouts are 5/20/10/5 seconds. Requests use `SOMA-MATER-Research/1.0`, no
environment proxies, authentication, browser rendering, stealth or impersonation.
Failures are isolated per publisher and audited; feed candidates remain usable.

This uses existing **httpx/lxml**, following the benchmark's transparent static
HTTP and DOM strategy. It does not import the benchmark or install Scrapling into
the production environment: Scrapling's CSS dependency conflicts with the current
readability dependency. HTTP transport parity with Scrapling/curl has **not** been
live-tested. There is no Scrapling article-body fallback.

The parser applies the benchmark's generic article-URL/card checks, rejects
navigation, author/category/tag/login/media/asset/event/job/collection routes,
and accepts only same-publisher HTTP(S) article links with usable headlines.
It considers at most **100 candidate anchor occurrences** after cheap link
prechecks and retains at most **20 distinct recent articles per publisher**.
Repeated image/navigation links do not become independent article candidates.
The cap is not an exhaustive discovery guarantee.

The existing `ARTICLE_FRESHNESS_DAYS` setting controls freshness (**7 by default**).
Only explicit zoned timestamps, visible publication dates and relative date
labels are accepted; site-wide dates, unzoned times and missing dates are skipped.
Card boundaries prevent a neighbouring story's date/snippet from being borrowed.
Dates beyond the run time are rejected. Day-only metadata is stored at UTC
midnight with `date_precision=day`; the entire dated day must lie within the
freshness window, so an uncertain cutoff day is skipped.

For The National, literal `/YYYY/MM/DD/` article-path dates retain the benchmark's
limited apparent-recency interpretation. Audit provenance explicitly says
`literal_url_path; apparent publication day only`; this is not an independently
verified publication timestamp. No other publisher receives that exception.

**Redirect limitation:** the benchmark observed The National's root Source URL
redirecting to `/uae/`. Under the explicit one-request rule, this is recorded as
`redirect_skipped_one_request_limit`; no second GET is sent. If the configured URL
still redirects, National contributes no direct supplement in that run. Its
normal feed is still collected. No registry URL was changed to avoid this limit.

## Merge before Luna

Feed collection completes before supplementary discovery. The combined pool
enters the existing objective prechecks and batched Luna classifier together.
Classifier model/batch size, prompts, enrichment budgets, scoring, regional
targets, publisher caps and existing same-event behavior are unchanged.

A feed/direct pair merges only within the same publisher identity when its
canonical URL is identical, or its **full normalized headline** matches and its
publication dates are within 24 hours. Actual publisher-suffix stripping reuses
the existing event helper; punctuation/case/Unicode normalization is followed by
exact equality. The broader fuzzy event threshold is not used to guess a direct
URL. Distinct, related and ambiguous many-to-one/one-to-many matches stay separate
for the existing later deduplication. These conservative rules may miss genuine
matches, especially edited headlines and indexing dates.

For a clear wrapper match, the representative uses the direct canonical URL and
`discovery_method=direct_site`. Its original `Article.url` remains the feed URL:
existing processed-URL checks can therefore still reject a previously handled
wrapper. Original feed title, publisher registration, rating, source hints,
image and feed-provided full article evidence are retained. A real listing
snippet is preferred when available, otherwise the feed snippet remains. Both
origins retain their own URLs, publication dates, snippets, discovery pages and
date provenance in memory. An already-direct feed canonical keeps its original
acquisition method and date. No feed-only story is removed or reordered by the
merge. Identical direct URLs are deduplicated during extraction.

## Audit and console

JSON and Markdown ingestion audits now distinguish `rss`, `google_news_rss`,
`direct_site` and `discovery_fallback`. Candidate records include canonical URL,
discovery page, date provenance/precision, `feed_wrapper_replaced` and origin
metadata. Origin snippets remain in memory and are omitted from the local audit;
no article bodies, credentials or raw provider exceptions are added.

Each of the four publishers has explicit discovery counters: feed candidates,
candidate anchors considered, distinct direct URLs found, recent accepted,
duplicate anchors, undated/stale/future rejections, headline matches, wrappers
replaced, direct-only candidates, ambiguous matches retained and duplicates
removed. Collection status, request count, HTTP status and duration are retained.
Inactive/not-due sources have zero counters and a status explaining the skip.

After selection, counters record direct candidates that reached Luna, detailed
enrichment, successful enrichment, ArticleRetriever attempts/raw extraction and
final selection. All four methods receive retrieval-status and selection counts.
Counts use candidate identities once across phases, rather than double-counting
reconsiderations. `not_attempted` and feed-provided content remain distinct from
HTTP retrieval. These are the existing retriever's raw statuses, **not** the
benchmark's independent page/paywall checks or a guarantee of complete evidence.
The terminal prints these counters only when the feature is enabled.

## Offline verification

`tests/test_hybrid_discovery.py` covers the ten requested scenarios, plus explicit
request/anchor/article limits, source allowlisting, redirect and access failures,
relative and National path dates, cutoff ambiguity, conservative matching,
preservation of direct/native feed metadata and processed-wrapper exclusion.
Configuration tests verify the default-off flag and invalid-value rejection.
Full ingestion tests use mocked classification/enrichment/retrieval and assert
zero Notion or ingestion-state writes. No paid live run is part of this change.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
git diff --check
```

## Next shadow run (not executed by this implementation)

This command collects configured feeds and permitted listing pages and makes
paid classifier/enrichment calls, while preserving Notion and ingestion state:

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:DIRECT_SITE_DISCOVERY_ENABLED = "true"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-sol"
.\.venv\Scripts\python.exe -X utf8 scripts\run_daily_ingestion_local.py --dry-run --all-sources --limit 12
```

No batch, enrichment, discovery or final-selection allowance is overridden by
that command. JSON/Markdown results remain under `.preview/ingestion_audits/`.
Set `$env:DIRECT_SITE_DISCOVERY_ENABLED = "false"` to restore the default path.

## Implementation files

- `.env.example`: documents the opt-in flag, without editing `.env`.
- `src/research_automation/config.py`: loads the default-off boolean.
- `src/research_automation/models/article.py`: in-memory acquisition provenance.
- `src/research_automation/sources/rss.py`: labels feed acquisition metadata.
- `src/research_automation/pipeline/discovery.py`: labels existing provider results.
- `src/research_automation/pipeline/direct_site_discovery.py`: bounded listing,
  freshness and conservative feed/direct merge.
- `src/research_automation/pipeline/ingestion.py`: shadow-only guard and integration
  before classification; console counters.
- `src/research_automation/pipeline/candidate_audit.py`: provenance and acquisition
  metrics in JSON/Markdown audits.
- `tests/test_hybrid_discovery.py` and `tests/test_config.py`: offline regressions.
- `README.md` and this document: usage, bounds and limitations.

The earlier discovery benchmark script, tests and saved artifacts are retained
unchanged. No source adapter is replaced and no Notion schema is modified.

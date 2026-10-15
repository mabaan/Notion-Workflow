# AGBI RSS verification — 15 October 2026

Implemented against clean local `main`, commit
`7c5ba0165d6ada76a90a1d5524467369cd6ec274` (`Iteration 3: Major Update`).
The local tracking reference `origin/main` points to the same commit; no remote
freshness claim is made. Recent preceding commits were `16ba7dc`, `d6b9253`,
`34cb57b`, and `2a5b378`.

The earlier relevance/ranking/significance, publisher retrieval, factual Research
Notes, evidence-grounded newsletter/SNS, advisory validation, and read-only
preview improvements are present. The baseline suite passed all 148 tests after
installing the already-declared `readability-lxml` dependency into this device's
virtual environment. No dependency declarations were changed. Pytest used a
workspace-local temporary directory because its default directory was inaccessible.

## Live endpoint checks

One GET per endpoint, using the existing RSS client's behavior: `httpx.Client`,
redirects enabled, default headers, and connect/read/write/pool timeouts of
5/20/10/5 seconds. No retries were made for either 403 response. The initial
sandbox socket restriction was resolved by running these two read-only requests
with network permission. These are actual publisher HTTP responses.

| Requested URL | HTTP | Final URL | Content-Type | Valid RSS | Parsed entries | Entries with content:encoded |
| --- | --- | --- | --- | --- | --- | --- |
| https://www.agbi.com/feed/ | 403 | https://www.agbi.com/feed/ | text/html | No | 0 | 0 |
| https://www.agbi.com/rss | 403 | https://www.agbi.com/rss | text/html | No | 0 | 0 |

**AGBI cannot currently be collected automatically from this environment.**
The downloaded XML's self link declares `https://www.agbi.com/feed/`. That is the
candidate Feed URL for the existing AGBI Source Registry record once Python
access is restored, but changing the URL alone does not resolve the current 403.
There is no verified working AGBI Feed URL to recommend configuring today.
No Notion records were read or changed during this task.

## Implementation and evidence limitations

- `sources/rss.py` reads feedparser's HTML `content` entries (including RSS
  `content:encoded`). It preserves the ordinary snippet, publication date,
  publisher attribution, and original article URL handling.
- `pipeline/article_retrieval.py` cleans feed HTML with the existing lxml
  dependency. Scripts, styles, navigation, forms, sidebars, hidden elements, and
  similar non-article elements are removed; entities are decoded and whitespace
  normalized. The existing limits are shared: 2,000,000 input bytes, at least
  300 cleaned characters, and at most 12,000 evidence characters.
- Usable text is carried in the existing `Article.article_text` field with
  `evidence_retrieval_status="feed_content"`. The existing retriever returns it
  before constructing an HTTP client or requesting an article page. There is no
  second enrichment path or additional LLM call.
- `clients/llm_client.py` supplies this text to the existing enrichment call with
  explicit feed provenance and a completeness limitation. Factual points,
  summary, relevance, significance, and other enrichment fields work normally.
- `utils/evidence.py` centralizes recognition of the in-memory `feed_content`
  and Research Notes `Feed Content` spellings and their limitation message.
- `pipeline/notion_write.py` stores concise factual points, URL, status, and the
  provenance/completeness message in Research Notes. It never stores article
  text. The Notion schema is unchanged.
- `pipeline/draft.py` recognizes those factual points as usable newsletter/SNS
  evidence and retains the completeness limitation. `pipeline/draft_validation.py`
  reports that limitation instead of treating feed content as failed retrieval.

The minimum length is a usefulness heuristic, **not proof of completeness**.
All accepted feed content is labeled: "Feed-provided article content;
completeness not verified. It may be an excerpt. Use only the supplied text."
Short/missing/oversized content keeps the existing article-page retrieval and
snippet fallback. Descriptions alone are not promoted to article evidence.
Substantial excerpts may be reused with that explicit limitation.

URL normalization, hashes, deduplication, ranking, geographic gates, regional
quotas, editorial prompt files, and image behavior were not changed. Feed URLs
are never substituted for article canonical URLs. No production ingestion or
live LLM calls were run.

## Offline downloaded-sample results

The user-supplied `agbi_feed_sample_2026-10-15.xml` is valid RSS 2.0 and contains
10 entries, all with HTML content. It is included under `tests/fixtures/` with
trailing line whitespace removed. No publisher-specific parser or headlines
were hardcoded into the implementation or tests.

Running the real `RssSource.collect()` with only its HTTP fetch replaced by the
local sample produced these results. Every row has status `feed_content` and a
distinct normalized publisher URL; **these are not successful live collection
results**. Bodies were not sent to Notion or an LLM.

| Normalized article URL | Cleaned characters |
| --- | ---: |
| https://www.agbi.com/banking-finance/2026/10/syrias-central-bank-issues-first-letter-of-credit-in-14-years | 1,515 |
| https://www.agbi.com/renewable-energy/2026/10/acwa-to-explore-solar-and-wind-projects-in-mongolia | 1,376 |
| https://www.agbi.com/oil-and-gas/2026/10/qatarenergy-reveals-steep-fall-in-profit-and-revenue | 2,141 |
| https://www.agbi.com/markets/2026/10/adia-backs-ipo-of-indias-zetwerk-as-anchor-investor | 1,784 |
| https://www.agbi.com/tech/2026/10/mubadalas-globalfoundries-lands-21bn-us-chip-project | 2,473 |
| https://www.agbi.com/shipping/2026/10/qatar-companies-get-grant-to-offset-higher-shipping-costs | 1,843 |
| https://www.agbi.com/oil-and-gas/2026/10/us-plans-to-ease-sanctions-on-shadow-fleet | 3,605 |
| https://www.agbi.com/oil-and-gas/2026/10/demand-destruction-an-indelicate-forecast | 3,866 |
| https://www.agbi.com/construction/2026/10/state-spending-cushions-gulf-projects-from-war | 2,385 |
| https://www.agbi.com/shipping/2026/10/two-vessels-sink-off-oman-as-hormuz-attacks-intensify | 3,575 |

Collection does not imply editorial eligibility: existing relevance and geographic
gates continue to decide which collected items can be shortlisted.

## Validation

- Baseline: **148 passed**.
- Focused collection/retrieval/evidence/drafting/validation/ingestion tests:
  **67 passed**.
- Full suite: **164 passed**.
- `git diff --check`: passed; new files also checked for whitespace errors.

Commands (PowerShell, repository root):

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_rss_content.py tests/test_article_retrieval.py tests/test_evidence.py tests/test_draft.py tests/test_draft_validation.py tests/test_collect.py tests/test_ingestion.py --basetemp=.local_state/pytest-agbi-focused-complete --tb=short
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.local_state/pytest-agbi-full-final --tb=short
git diff --check
```

`tests/test_rss_content.py` covers HTML cleaning, descriptions and short content,
size/length limits, the real AGBI fixture, single-call enrichment without article
HTTP, canonical hashes and duplicates, mocked Research Notes round trips,
newsletter/SNS evidence, excerpt limitations, and non-retried 403/405 collection
failures alongside a working source. `tests/test_ingestion.py` additionally
checks that an AGBI 403 completes the ingestion orchestration with mocked HTTP
and Notion, without enrichment, retries, writes, or deduplication-store changes.

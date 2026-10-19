# Quality backfill and relevance/significance correction

Inspected exact source: [20261018T224853375008Z_8195c1ae.json](../ingestion_audits/20261018T224853375008Z_8195c1ae.json); SHA-256 `b44aef8412b51840ad27e220c0ff7d78efe42434c3bac8a391c66f9b2ff0dc13`.

The original audit and ingestion state were not modified. Detailed original candidate rows are in [analysis.json](analysis.json). This pass uses offline/mocked tests only; no new classifier/enrichment/provider calls or Notion writes occurred.

## Why KSA consumed 17 attempts with zero qualifications

| Region | Enriched | Qualified |
|---|---:|---:|
| Global | 9 | 4 |
| UAE | 18 | 2 |
| KSA | 17 | 0 |
| Egypt | 4 | 1 |

The prior adaptive loop passed current regional shortages into the same allocator used for initial coverage. Each allocation reset its regional opportunity counters and reserved up to two assessments per remaining deficit. KSA never qualified a story, so its three-slot deficit kept renewing that priority. Initial source round-robin could also place a new publisher ahead of a higher classifier tier. Meanwhile Global coverage was already satisfied, so its remaining candidates lost those regional reservations despite permitted final overflow.

Of KSA's 17 attempts, one was Relevant/5 (agricultural-production support), one Relevant/4 (the pomegranate festival), 12 Borderline/3, and three Borderline/2. Final relevance was 3 for four and 2 for thirteen; none reached its unchanged threshold. Thirteen KSA candidates came from RSS and four from discovery. The audit retains source phase and ranks but not an immutable chronological attempt number, so it cannot prove which individual calls occurred before versus after attempt 32. No artificial call chronology is supplied.

The Saudi agricultural-support report was rejected at relevance 3/significance 3 while its significance rationale cited missing timeframe, allocation and production impact. The revised prompt addresses that conceptual conflation when evidence directly supports the agricultural use. The National Veal funding report already survived at relevance 4/significance 2 and remains a positive regression.

## Exact allocation behavior

- Initial allowance remains 32. Keep the current first RSS allocation (24 by default), discovery only when needed, merged RSS/discovery pool, regional opportunities and source round-robin for the remainder of the initial allowance. All classifier batches finish before allocation.
- After the initial allowance, merge every remaining eligible Relevant/Borderline candidate across regions and source phases. Do not reserve opportunities for any regional deficit.
- Use a simple lexicographic ordering: decision, classifier score, publisher attempt/weekly count within equal tiers, publisher quality, publication freshness, shortage boolean as a final tie-break, stable canonical URL. This creates no new score formula.
- Enrich in batches of eight, up to 48 attempts total. Existing final selection is checked after each attempt. Stop when enough unique viable winners exist under event/publisher/run constraints, when the ceiling is reached, or when the eligible pool is exhausted. Failed attempts still count; already attempted articles remain excluded.
- The final 70/20/10 score uses detailed enrichment, not classifier scores. Coverage-first allocation and overflow, thresholds 4/5, publisher cap two, same-event logic, provider limits and deterministic rollback are unchanged.

## Prompt changes

Detailed enrichment now says:

> Do not reduce relevance merely because scale, timeframe, implementation details, quantified impact or expected outcomes are missing when the supplied evidence clearly establishes a concrete direct development in a core mission sector. Reflect those evidence or scale limitations in editorial significance instead.

General examples distinguish supported agricultural/livestock financing and water infrastructure (relevance at least 4, potentially significance 2-3) from green bonds without mission-linked proceeds or generic sustainability statements (mission fit may still be 3 or lower). Missing evidence of the actual sector connection remains a relevance limitation. No observed headline is hardcoded.

First-stage classification now defaults routine one-off basket, hot-meal and water-delivery stories to Borderline around 3. It explicitly preserves eligibility and high recall. Broader food access/malnutrition changes, halted/restored commercial supplies, major programme expansions, structural water access, policy/financing and regional supply-system consequences can receive Relevant 4/5. The old audit contains eight routine delivery stories scored Relevant: seven at 4 and one at 5. They are not relabelled as fresh model results here.

## Exact files changed in this pass

- `src/research_automation/pipeline/luna_selection.py`: explicit quality-backfill allocation; regional reservations disabled only in that phase.
- `src/research_automation/pipeline/ingestion.py`: select quality-backfill mode only in the adaptive loop after the initial allowance.
- `src/research_automation/prompts/article_enrichment.txt`: stronger fit-versus-significance distinction and general examples.
- `src/research_automation/prompts/article_classification.txt`: recall-preserving routine humanitarian calibration.
- `tests/test_luna_quality_backfill.py`: 18 new offline/mocked regressions.
- `docs/luna_selection.md`: current policy, audit findings and historical correction boundaries.
- `.preview/luna_quality_backfill/`: analysis, report and integrity records; historical audits remain intact.

## Verification and limits

**428 tests passed** (410 before this pass); **git diff --check passed**.

Five allocation tests verify initial regional opportunities; Global Relevant/5 ahead of KSA Borderline/3 even with an open shortage and lower publisher-use advantage; merged eight-candidate picks across regions and RSS/discovery phases; publisher diversity and shortage tie-break order; the real orchestrator's 32-attempt transition, two global backfill batches, no repeats and 48 maximum. Five enrichment cases verify delivery of the revised rubric through the real prompt/parser and unchanged threshold. Eight humanitarian cases verify fixed routine Borderline and broader Relevant outputs, strict classifier transport/schema, and continued enrichment eligibility. The existing suite still verifies early stop, publisher limits, final coverage/overflow, deduplication, rollback and dry-run safety.

Mocked outputs test mechanics and prompt delivery, not real editorial accuracy or guaranteed relief from threshold variability. The audit omits original snippets/bodies and detailed attempt chronology. We do not invent these or project a new winner count from old scores. Source diversity applies within equal editorial tiers during backfill; stronger tiers can receive more calls. The maximum bounds attempts rather than dollars or tokens.

Original audit/state and unchanged selection/config/discovery/ranking hashes are recorded in [integrity.json](integrity.json).

## Next user-launched shadow dry run

Run from the repository root. This can incur API costs; it was not executed in this pass. Existing credentials are loaded from `.env`.

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-luna"
$env:CLASSIFICATION_BATCH_SIZE = "100"
$env:CLASSIFICATION_TIMEOUT_SECONDS = "120"
$env:ARTICLE_ENRICHMENT_INITIAL_BUDGET = "32"
$env:ARTICLE_ENRICHMENT_MAX_BUDGET = "48"
$env:ARTICLE_ENRICHMENT_BACKFILL_BATCH = "8"
$env:MIN_ARTICLE_RELEVANCE_SCORE = "4"
.\.venv\Scripts\python.exe -m scripts.run_daily_ingestion_local --dry-run --all-sources --limit 12
```

`--limit` controls winners, not model spend. Dry run performs read-only source/queue queries and writes local metadata audits outside ingestion state. The default mode remains deterministic.

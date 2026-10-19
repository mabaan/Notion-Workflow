# Luna article selection

`ARTICLE_SELECTION_MODE=luna` enables metadata classification followed by bounded
detailed enrichment. The shipped default remains `deterministic` for rollback.
Classifier and enrichment are the only model stages.

## Flow and assessment budget

1. Read the current Dataset Meeting's queue state before weekly setup can write.
2. Compute remaining weekly capacity from actual Global/UAE/KSA/Egypt counts,
   including overflow. Effective capacity is the minimum of remaining weekly
   capacity, requested `--limit` and `MAX_ARTICLES_PER_RUN`. If it is zero, skip
   setup writes, collection, classification, retrieval, enrichment and discovery;
   still produce a local diagnostic audit.
3. Collect due publisher feeds and apply only objective prechecks: valid URL/title/
   publication date, freshness, exact/canonical duplicates, processed URLs/hashes
   and self-published domains. No deterministic keyword/geography gate runs here.
4. Classify every eligible metadata record in batches of at most 100 and merge all
   outcomes before allocation. Explicit Irrelevant results stop here; Relevant,
   Borderline and unresolved request failures remain eligible for bounded review.
   Failed outcomes have no invented score and remain visible in diagnostics.
5. Allocate an initial 32 enrichment attempts with regional opportunities and
   source diversity. Up to three quarters of that initial allowance goes to the
   first RSS assessment; the remainder can assess discovery or deferred RSS.
6. If unique strict winners still do not fill capacity, backfill in batches of 8
   up to 48 total attempts. Adaptive backfill ranks all remaining eligible RSS/
   discovery candidates together: Relevant before Borderline, classifier score,
   soft publisher diversity, publisher quality, recency, then regional shortage
   as a tie-break before stable URL ordering. It has no regional reservations.
7. Retrieve evidence only for allocated candidates, enrich once per candidate,
   and recompute strict constrained selection after each attempt. Failed calls
   count; canonical duplicates skipped before enrichment remain backfillable.
   Stop when strict capacity is full, the pool is exhausted or the budget is spent.
8. Run strict/fallback final selection, then write complete winners to Article
   Queue for human review. Record processed URLs only after successful creation.

Publisher caps apply at final selection; assessment uses soft diversity so a
publisher's later, stronger article can still be assessed. Brave and NewsAPI keep
their existing 20-request defaults, ordering and collection limits. Discovery
query countries are hints, never geographic proof. Attempt limits are not billing
or token caps, and classification covers the full objectively eligible pool.

## Current editorial scope

Both stages return `story_type` and `is_new_development` (`true`, `false`, or
`"unclear"`). Metadata classification favors recall; detailed enrichment makes the
final evidence-based judgment. The existing enrichment call supports Luna or Sol.

Both final tiers exclude novelty `false` and primary `politics_diplomacy`,
`conflict_security`, `humanitarian_relief` or `routine_event` stories. Background/
opinion types require novelty explicitly `true`. Mission types with novelty
`"unclear"` still face the existing thresholds and conservative significance.

Mission keywords alone do not establish relevance. Conflict coverage needs a
supported material system consequence as its primary news, such as a production,
fertilizer, commercial-food, water-infrastructure or transition-system disruption.
Farmer attacks or local damage counts alone do not establish system impact.
Autonomous/AI transport labels need a supported clean-transport consequence, and
generic property portfolios need a central mission investment.

Substantive sector policy, financing, projects, practical research, systemic
climate measurements and transition-material investigations can qualify. Missing
scale, timing or quantified impact lowers significance separately from an already
supported core mission fit. Primary relief or conflict remains excluded.

Malformed detailed scope fields fail through the existing error path, without a
repair call. Historical dataclass objects default to `other`/`"unclear"`; they are
not retroactively reclassified. No Notion property is added.

## Final selection: strict and fallback

Strict qualification requires final relevance at least **4 for registered
publishers** or **5 for unregistered publishers**. Select strict coverage winners
and strict quality overflow first. Reserve them before fallback so a fallback
story cannot consume a strict winner's slot, publisher allowance or event.

Fallback is available only in Luna mode, only after assessment has finished and
only for spare capacity. A candidate must already be enriched, have a registered
publisher, final relevance at least **3**, final significance at least **3**, and a
valid Global/UAE/KSA/Egypt region. It can override only the strict relevance
rejection. Objective/processed/URL/event exclusions, weekly publisher cap,
editorial scope and any recorded `publication_failure_reason` still apply.
An invalid-URL retrieval status prevents fallback; a blocked fetch alone is not a
factual verdict. There is no separate structured factual-verification verdict.

Fallback pursues regional shortages first, then participates in quality overflow
across regions. Both tiers use the existing score:

```text
100 * (0.70 * final_relevance/5 + 0.20 * final_significance/5 + 0.10 * publisher_quality/10)
```

Targets default to Global 3, UAE 4, KSA 3, Egypt 2; two articles per publisher per
week remain the cap. Regional overflow is allowed within total weekly capacity.
For existing counts 6/1/1/1, a limit of 12 permits at most three new articles.
Twelve strict winners use no fallback. Four strict plus five eligible fallback
produce nine; a limit is never a requirement. No article is enriched again.
Deterministic rollback remains strict-only with regional ceilings.

## Configuration and commands

| Setting | Default | Meaning |
|---|---|---|
| `ARTICLE_SELECTION_MODE` | `deterministic` | Set `luna` to enable this path |
| `CLASSIFICATION_MODEL` | `gpt-6-luna` | Required classifier in Luna mode |
| `CLASSIFICATION_BATCH_SIZE` | `100` | Maximum initial metadata batch |
| `LLM_MODEL` | `gpt-6-luna` | Luna mode also accepts `gpt-6-sol` enrichment |
| `ARTICLE_ENRICHMENT_INITIAL_BUDGET` | `32` | Initial assessment allowance |
| `ARTICLE_ENRICHMENT_MAX_BUDGET` | `48` | Hard attempt ceiling; cannot exceed 48 |
| `ARTICLE_ENRICHMENT_BACKFILL_BATCH` | `8` | Adaptive assessment batch |
| `MIN_ARTICLE_RELEVANCE_SCORE` | `4` | Registered strict threshold; cannot be lowered in Luna mode |

`ARTICLE_ENRICHMENT_BUDGET` is the legacy initial-budget alias, used when the new
initial variable is absent. Set initial and maximum equal for fixed-attempt
behavior. Classifier request/retry settings are in [classifier documentation](article_classifier.md).

Use the [README ingestion settings and commands](../README.md#run-ingestion)
for the current Luna classifier/Sol enrichment session and optional URL resolution.

Remove `--dry-run` to save qualified articles to Article Queue. Dry runs make no
Notion or persistent ingestion-state writes, but can spend on model/discovery
requests. `--all-sources` bypasses scheduling only; it does not ignore existing
queue/history or capacity. `--dry-run --no-enrich` skips both model stages and
discovery. Roll back with `$env:ARTICLE_SELECTION_MODE = "deterministic"`.

## Audits and limitations

Console output reports weekly target, existing total, remaining capacity,
requested limit, effective capacity, and strict/fallback/total selections.
Metadata-only JSON/Markdown audits under ignored `.preview/ingestion_audits/`
record objective exclusions, classifier fields/errors, enrichment scores and
evidence status, final constraints, overflow, tier and fallback reason. They also
record classifier models, requests and reported tokens. Missing usage stays
explicit; bodies, snippets, credentials and raw provider errors are not saved.

Sparse snippets, model mistakes, uncertain geography and title-based event
matching remain limitations. Unassessed candidates and unresolved failures stay
visible. Offline tests verify mechanics with mocked judgments; they do not prove
editorial accuracy. See [evaluation tooling](evaluation.md) for retained fixtures
and historical capture handling.

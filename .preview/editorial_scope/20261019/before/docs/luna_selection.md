# Controlled Luna selection

## Current final selection: strict and fallback tiers

Final Luna selection now preserves all winners from the existing strict coverage
and quality-overflow selection, then uses spare run capacity for already-enriched
fallback candidates. Strict relevance remains **4 for registered publishers and 5
for unregistered publishers**. Strict winners, including overflow reservations,
always have priority over fallback coverage and score. This reservation prevents
a fallback article from taking a strict winner's slot, publisher allowance or
event representation.

Fallback requires final relevance **at least 3**, final editorial significance
**at least 3**, a registered publisher, and one of Global/UAE/KSA/Egypt. It cannot
override any rejection except the strict relevance threshold. Existing URL,
processed-article, event and weekly publisher constraints still apply. A recorded
`publication_failure_reason`, an objective-cleanup rejection or an invalid-URL
retrieval status prevents fallback. A blocked fetch alone is not a factual verdict.
Ingestion has no structured factual-verification verdict today; this change does
not add one or interpret free-text summaries as such a verdict.

After protecting strict winners, fallback first pursues remaining regional
shortages using the existing coverage allocator, then fills any remaining capacity
by the unchanged **70/20/10 queue score** across regions. The requested limit is
only a maximum: four strict plus five eligible fallback articles produce nine.
Twelve strict winners use no fallback. No candidate is enriched again.

The enrichment stop condition, discovery decisions and allocation continue to use
strict winners. The initial **32**, maximum **48** and backfill batch **8** remain
unchanged, as do default Luna models, classifier batch **100**, prompts, quotas and
event matching. Fallback runs only after those assessment decisions finish.
Deterministic rollback selection remains strict-only.

An explicit `LLM_MODEL=gpt-6-sol` override is also supported for enrichment while
`CLASSIFICATION_MODEL=gpt-6-luna` retains the classifier. Both use supported
`reasoning_effort=medium` requests without sampling parameters; defaults and
selection rules are unchanged.

Console output separates strict/fallback/total counts. JSON and Markdown audits
retain the selected tier and fallback reason alongside classifier score, final
relevance/significance, publisher rating, queue score and region. A selected
fallback keeps its original strict rejection separately from its final selection
decision. Tier/reason also enter the existing optional selection-reason text;
the Notion schema is unchanged.

See the [two-tier implementation report](../.preview/luna_two_tier/report.md) for
the exact algorithm, changed files, regression results and next dry-run command.
The sections below describe earlier steps; their strict-only final-selection
statements are superseded by this section.

## Current quality-backfill correction (Step 5)

The second real shadow audit (`20261018T224853375008Z_8195c1ae`) reached 48 attempts: Global 9/4 qualified, UAE 18/2, KSA 17/0, Egypt 4/1, with five final winners after event suppression. KSA's 17 assessments included 15 Borderline candidates. The allocator reapplied its regional reservations on every adaptive batch; the unmet KSA target kept receiving opportunities even with higher-classified Global candidates left. The audit does not retain a complete chronological attempt log, so exact initial-versus-adaptive counts cannot be reconstructed from it. The code-level cause and recorded candidate outcomes are documented in [the quality-backfill report](../.preview/luna_quality_backfill/report.md).

The initial allowance remains **32** with the existing regional opportunities and RSS/discovery allocation. **After that initial allowance**, all remaining eligible classified candidates are ranked together, across regions and RSS/discovery phases:

1. Relevant before Borderline.
2. Higher classifier relevance.
3. Soft publisher diversity within equal decision/score tiers, carrying prior attempt and weekly counts.
4. Publisher quality, then recency.
5. Whether a region remains short, only as a tie-break before stable URL ordering.

There are no regional reservations in adaptive backfill. Batches remain **8** and the hard attempt maximum remains **48**. The existing constrained selector still determines when enough unique viable winners exist; failed attempts count, duplicates are not enriched twice, and the run stops as soon as it is full, the pool is exhausted, or the ceiling is reached. Initial regional allocation and final coverage-first/overflow selection remain unchanged.

The enrichment prompt now explicitly directs missing scale, timeframe, implementation detail, quantified impact or expected outcomes into **significance** when a concrete core mission development is already supported. Direct agricultural/livestock financing or a water-infrastructure investment can remain relevance 4 with significance 2-3. A green bond with no mission-linked use of proceeds or generic sustainability wording can still be relevance 3 or lower. No observed headline was added to production rules.

The classifier now defaults routine one-off food baskets, hot-meal batches and isolated water deliveries to **Borderline, around 3**. They remain eligible. Broader access or malnutrition changes, commercial supply restoration/halts, major programme expansion, infrastructure, policy/financing or regional supply effects can receive Relevant 4/5. The audit contained eight routine delivery headlines scored Relevant (seven at 4, one at 5); revised model judgments have not been measured.

Verification: **428 offline tests passed**, including 18 new allocation, enrichment-rubric and humanitarian-classifier regressions; `git diff --check` passed. No paid calls, Notion writes or ingestion-state mutations were performed. Same-event logic, configuration, discovery limits and final scoring/selection are unchanged. Integrity checks and the exact next dry-run command are in the linked report; the Step 4 command below remains valid with the unchanged 32/48/8 settings.

## Previous downstream corrections (Step 4)

The Step 4 publisher round-robin description below still applies to the initial allocation. Step 5 above supersedes it for adaptive backfill after the initial budget. Its historical measurements and test total are preserved.

The first real shadow audit was inspected before these corrections. Its 76 budget deferrals contained seven Relevant/4 candidates and 69 Borderline candidates. Its 38 premature cap rejections were 25 Reuters and 13 Saudi Press Agency. Some merit further assessment, but absent final scores do not prove that they outrank the winners. The recorded same-event rejection was Arab News' Gaza-malnutrition report in favor of Reuters; the UAE strategy pair escaped the old check. Full ranked lists, known-example fates, limitations and the exact change report are in [the shadow correction report](../.preview/luna_shadow_corrections/report.md).

The architecture, Luna classifier/batch size, thresholds (4/5), scoring (70/20/10), coverage-first/overflow selection, final publisher cap, provider limits and default deterministic mode remain. The focused corrections are:

- Publisher caps apply at final selection. Enrichment uses soft publisher round-robin, carrying existing weekly counts and previous attempts across allocation batches. Classifier decision/score, source quality and freshness rank candidates on each publisher's turn. Later candidates from the same source can be assessed; all are still subject to the final cap of two, including existing weekly counts.
- The initial budget is **32**, retaining the initial RSS/fallback allocation. If the requested number of viable unique winners is still missing and unassessed Relevant/Borderline candidates remain, add batches of **8**, to a hard maximum of **48** attempts. Recompute final constrained selection after every attempt and stop immediately once capacity is filled. Failed calls count and candidates are not enriched twice.
- The enrichment rubric reserves relevance 4 for substantive mission developments. Routine festivals, seasonal/landscape coverage, ordinary labels and local sales or relief-delivery counts generally stay at most 3 without supported broader consequences. Financing, capacity, deployment, food policy, structural malnutrition/access and material supply changes can qualify; no headline/category blacklist was added.
- Current-pool event comparison retains exact URL and title checks, adds conflicting-country/like-unit-measure safeguards, and recognizes closely timed policy reports with shared action, geography and strong title/snippet overlap. Existing queue records still use their available title context. The recorded UAE pair now yields the stronger AGBI representative. The saved-score replay changes eight winners to seven; it does not predict new model scores.

| Configuration | Default | Meaning |
|---|---|---|
| `ARTICLE_ENRICHMENT_INITIAL_BUDGET` | `32` | Initial RSS plus fallback assessment allowance |
| `ARTICLE_ENRICHMENT_MAX_BUDGET` | `48` | Total hard attempt ceiling; values above 48 are rejected |
| `ARTICLE_ENRICHMENT_BACKFILL_BATCH` | `8` | Additional assessment opportunities per backfill batch |
| `ARTICLE_ENRICHMENT_BUDGET` | `32` | Legacy alias for initial budget, used only when the new initial variable is absent |

Set initial and maximum equal for fixed-attempt behavior. Attempt limits are not dollar/token limits. Audits and console output show initial, maximum, batch size and actual attempted counts. All **410 offline tests pass**; `git diff --check` passes. No paid requests, Notion writes or persistent ingestion-state changes were made for the correction pass.

Next user-launched dry run, from the repository root (uses existing `.env` credentials):

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

## Historical Step 3 implementation report

The report below records the original integration. Its fixed 32-attempt ceiling, pre-enrichment publisher cap and decision-tier diversity description are superseded by Step 4 above. Historical test totals and measurements are retained as originally reported.

Luna selection is implemented behind `ARTICLE_SELECTION_MODE=luna`. The default remains `deterministic`. No live API evaluation or production run was performed for this change; all new model responses were mocked. Existing evaluation captures remain historical evidence, not measurements of this revised prompt or allocator.

## Architecture

1. Load due publisher sources and current weekly URL/event/publisher context; collect RSS.
2. Perform objective URL, meaningful-title, publication-date, freshness, exact/canonical duplicate, processed URL/hash and SOMA MATER domain checks.
3. Classify **every** remaining RSS metadata record with GPT-6 Luna, in batches of at most 100. No keyword or deterministic geography gate runs here. Inputs contain stable canonical-URL hash IDs, titles, actual snippets, publishers, dates and explicitly non-evidential source hints; no full bodies.
4. Merge **all** RSS batch outcomes before any enrichment allocation. Retain Relevant and Borderline candidates. Explicit Irrelevant decisions stop here.
5. Allocate a bounded, source-diverse detailed-enrichment pool. Retrieve evidence only for allocated candidates, checking canonical URLs and self-publication again after resolution. Existing queue events and exhausted publisher caps can avoid unnecessary detailed calls after classification.
6. Run the existing GPT-6 Luna enrichment stage. Its final relevance, significance, summary, factual points and angles are authoritative. Classifier scores never enter the final 70/20/10 score.
7. If qualified coverage/run capacity is still short and assessment budget remains, invoke the existing Brave/NewsAPI fallback once for the deficient regions. Classify all discovered metadata with the same classifier. Merge those outcomes with deferred RSS candidates before allocating the remaining assessment budget. RSS is not reclassified or enriched twice.
8. Select regional coverage first, then strongest remaining qualified articles as overflow. Both passes enforce the same existing URL/event suppression, weekly publisher cap and run maximum.
9. Write winners only in live mode through the existing Notion writer. Dry runs read Notion but write only local diagnostic audits, outside ingestion state.

The pre-existing classifier's strict JSON schema, exact ID coverage, missing/unknown/duplicate ID checks, bounded retry/splitting, model IDs and token/request accounting remain. A malformed batch must recover before its results are used. SDK classifier retries remain disabled; the component owns retries.

Operational failures are not Irrelevant decisions. They receive no invented classifier score or country. They rank after classified candidates and may receive existing detailed assessment within the same budget. Unassessed failures remain explicitly deferred, with IDs/error categories in the audit. Borderline/failed candidates with unclear geography get no source-country fallback: detailed evidence must produce one compatible region, otherwise the candidate remains unselected. For a valid classifier region, that region controls routing and the initial Notion payload.

## Configuration and rollback

| Setting | Default | Behavior |
|---|---|---|
| `ARTICLE_SELECTION_MODE` | `deterministic` | `luna` enables classification and coverage overflow; `deterministic` restores the keyword/routing path and hard regional ceilings |
| `ARTICLE_ENRICHMENT_BUDGET` | `32` | Total detailed-enrichment attempts across RSS and fallback, including failed attempts |
| `CLASSIFICATION_MODEL` | `gpt-6-luna` | Required in Luna mode; no alternate production classifier model |
| `LLM_MODEL` | `gpt-6-luna` | Required in Luna mode for detailed enrichment |
| `CLASSIFICATION_BATCH_SIZE` | `100` | Initial maximum group size; all groups are processed |
| `CLASSIFICATION_MAX_REQUEST_BYTES` | `200000` | Serialized UTF-8 request preflight limit |
| `CLASSIFICATION_MAX_OUTPUT_TOKENS` | `32768` | Output including reasoning; estimated output also constrains grouping |
| `CLASSIFICATION_MAX_ATTEMPTS` | `2` | Including first attempt, at most 3 configurable per sub-batch |
| `CLASSIFICATION_TIMEOUT_SECONDS` | `120` | Increased from 60 because evaluated full batches took about 73 seconds |
| `MIN_ARTICLE_RELEVANCE_SCORE` | `4` | Cannot be below 4 in Luna mode; unknown publishers still require 5 |

The classifier automatically bisects groups that exceed request/context/output estimates or encounter truncation. Malformed replies receive bounded retries and smaller-group recovery; transient transport/rate-limit failures are bounded. See [classifier contracts](article_classifier.md) for detailed recovery semantics. A persistently malformed N-article group can require up to `max_attempts * (2*N - 1)` requests. There is no model voting or third LLM stage.

The 32-attempt default preserves the previous maximum aggregate of four regions times eight attempts. It changes those regional ceilings into a shared budget. Up to `ceil(3 * budget / 4)` attempts go to the first RSS assessment: 24 by default, matching the prior four times six initial opportunities. The remaining eight are available for fallback and deferred RSS when coverage is short. Unused capacity is not filled with Irrelevant metadata. Smaller positive budgets are supported; they can limit achievable coverage. The legacy initial/max-per-region enrichment settings continue to govern deterministic mode. `ARTICLE_SHORTLIST_MAX_PER_REGION` also retains its existing discovery collection limit (8); it is not a Luna enrichment ceiling.

Allocation reserves up to two assessment opportunities per remaining regional target, subject to available candidates and the shared phase budget. Empty regions release capacity globally. Within each choice, classifier decision and relevance lead, followed by publisher round-robin within the same decision/score tier, publisher quality, freshness and a stable URL tie-break. These are assessment opportunities, not guaranteed selections. The second phase uses remaining coverage deficits and the current provisional publisher/event context. An unassessed candidate is explicitly deferred when cost/run limits stop assessment.

Brave and NewsAPI retain their configured 20-request defaults and existing provider ordering/limits. Discovery query countries remain hints, never factual geography. Sufficient qualified RSS coverage or a full run avoids discovery; a spent enrichment budget also prevents a pointless fallback.

## Enrichment calibration

The shared enrichment prompt now distinguishes:

| Relevance | Meaning |
|---|---|
| 5 | Central, strategically important mission development in scope |
| 4 | Clearly supported concrete core mission development, including government agricultural/livestock/fisheries funding, production capacity, water infrastructure, renewable/storage investment, policy/regulation or transition manufacturing |
| 3 | Adjacent, secondary, primarily commentary, weakly evidenced, or limited/incremental coverage without a clear core mission consequence |
| 1–2 | Incidental or off-mandate |

Literal phrases such as “food security” and “net zero” are unnecessary when the production/resource/transition connection is supported. Missing scale or novelty can lower significance independently without reducing clearly supported core financing to relevance 3. Unsupported practical applications and vague funding uses still receive conservative assessment. The prompt preserves stage/status distinctions, evidence limitations and the requirement to state the mission bridge in `why_it_matters`.

The National Veal headline appears only in tests/evaluation data. A fixed relevance-4, significance-2 enrichment qualifies; an otherwise identical relevance-3 output fails. This tests the rubric delivery, parser and threshold behavior, and does not prove the real model will always score the headline consistently. The calibrated prompt is shared by both selection modes; rollback preserves deterministic screening/allocation rather than reverting this requested prompt improvement.

Relevance remains the existing hard editorial qualification gate. Significance remains separate and ranks candidates through the unchanged **70% final relevance / 20% significance / 10% publisher quality** score; no new significance cutoff was invented. Overflow has the same qualification requirements as ordinary coverage and cannot admit relevance 3.

## Coverage and overflow

Pass 1 retains the existing deterministic scarce-region-first allocation, choosing the strongest candidate available in each chosen region. It tries Global 3, UAE 4, KSA 3, Egypt 2. Pass 2 then uses the same final-score ordering across all remaining qualified regions, subject to publisher, event and run limits. The strongest representative survives an event cluster. Overflow is flagged in audits, console winners and the existing optional selection reason; there is no schema change.

| Qualified fixture | Deterministic mode | Luna mode |
|---|---|---|
| G3 / U4 / K3 / E2 | 12, exact coverage | 12, exact coverage; no overflow |
| G5 / U3 / K2 / E2 | 10; Global capped at 3 | 12; two Global overflow selections |
| One publisher has four otherwise qualified stories, weekly cap 2 | At most 2 | At most 2, including overflow |
| A duplicate of an existing weekly event | Suppressed | Suppressed, including overflow |

Coverage shortages remain visible even when overflow fills total run capacity. Existing weekly region/publisher counts inform both passes. No new weekly volume ceiling was added: the existing per-run maximum and weekly publisher cap remain the hard volume controls; once all regional targets are already satisfied at run start, model assessment is skipped as before.

## Audits and verification

The existing Markdown/JSON candidate audits now include selection mode; objective rejection; classification attempted, decision, score, region, topic, justification/error; shortlist and actual enrichment attempt; final relevance and significance; individual final constraint/rejection; selected status; overflow flag; requested/returned classifier model, batch IDs, request status, split count and reported token usage. No full article bodies, raw API errors or extra model requests are included. Failed requests without provider usage remain explicitly counted rather than estimated as known usage.

Full offline verification: **372 passed**, versus 326 before this step; `git diff --check` passed. The 39 new integration/selection cases plus seven configuration cases cover all requested behaviors: missing keywords, incidental-keyword rejection, other-MENA and country routing, source-hint separation, 103 inputs across 100+3 batches, complete merge before allocation, malformed ID recovery, partial failure retention, ambiguous geography, funding relevance 4 versus 3, unchanged unknown-publisher gate, objective cleanup/processed hashes, source quality/freshness/diversity/order independence, shared failed-attempt budget, canonical resolution, discovery classification/skip, normal coverage, overflow/run/publisher/event constraints, safe dry run, audit contents and legacy rollback. Existing classifier tests continue to cover unknown IDs and unrecoverable malformed responses. The CLI help command was also checked without collection or API calls. Persistent ingestion-state hashes still match the completed evaluation.

Three prior tests were adjusted for the new defaults/prompt size: the output-limit rejection uses Luna's limit, the mini pricing test names mini explicitly, and the fixed-budget evaluation preflight uses varied saved metadata rather than 100 copies of one unusually long record. Evaluation budgets and saved results were not changed.

## Files changed in this step

Earlier classifier/evaluation work was preserved. This list identifies the files changed by this integration step, including edits to files that were already uncommitted:

| File | Change |
|---|---|
| `.env.example` | Opt-in mode, shared budget, Luna defaults and timeout |
| `src/research_automation/config.py` | Load and validate rollout/model/budget/threshold settings |
| `src/research_automation/clients/article_classifier.py` | Update component description for integration |
| `src/research_automation/models/candidate.py` | Classification, objective rejection, selection and overflow diagnostics |
| `src/research_automation/pipeline/article_classification.py` | Indexed precheck exclusions; meaningful title validation |
| `src/research_automation/pipeline/luna_selection.py` | New cleanup/classification/merged allocation/enrichment adapter |
| `src/research_automation/pipeline/ingestion.py` | Mode dispatch, shared fallback budget, request reporting |
| `src/research_automation/pipeline/selection.py` | Optional second coverage-overflow pass and individual constraint reasons |
| `src/research_automation/pipeline/candidate_audit.py` | Model ledger and readable per-article path, safe invalid-URL diagnostics |
| `src/research_automation/prompts/article_classification.txt` | General production/livestock/fisheries/transition examples |
| `src/research_automation/prompts/article_enrichment.txt` | Evidence-grounded relevance-4 calibration, separate significance, data trust |
| `scripts/run_daily_ingestion_local.py` | Clarify that `--no-enrich` skips both model stages |
| `tests/test_luna_selection.py` | New mocked integration and two-pass selection coverage |
| `tests/test_config.py` | Defaults, rollout configuration and invalid-setting coverage |
| `tests/test_article_classifier.py` | Validate the Luna output-limit boundary |
| `tests/test_classifier_evaluation.py` | Explicit historical mini pricing fixture |
| `tests/test_luna_followup_evaluation.py` | Varied metadata in bounded offline preflight |
| `docs/luna_selection.md` | This architecture, verification and rollout report |
| `docs/article_classifier.md` | Current defaults and integration link; historical experiments preserved |
| `docs/candidate_selection_routing.md` | Identify legacy routing scope and link Luna mode |
| `README.md` | Entry point to mode-specific behavior |

## Controlled dry run and recommendation

No paid dry run was launched: the completed evaluation's budget is not authorization for a new ingestion experiment. From the repository root, the following PowerShell commands use the existing `.env` credentials, force the intended models, and explicitly avoid writes. `--all-sources` makes this a useful pool review even if publishers are not due. It can incur classifier/enrichment, discovery and publisher-fetch costs. The enrichment attempt limit is not a dollar/token cap; classification processes the full objectively eligible feed pool. `--limit` caps winners, not API requests.

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-luna"
$env:CLASSIFICATION_BATCH_SIZE = "100"
$env:CLASSIFICATION_TIMEOUT_SECONDS = "120"
$env:ARTICLE_ENRICHMENT_BUDGET = "32"
$env:MIN_ARTICLE_RELEVANCE_SCORE = "4"
.\.venv\Scripts\python.exe -m scripts.run_daily_ingestion_local --dry-run --all-sources --limit 12
```

The command does not update source health, weekly pages, Article Queue, processed URL state or article assets. It creates metadata-only diagnostic Markdown/JSON under `.preview/ingestion_audits/` beside the configured local-state directory. Repeated dry runs can spend again because they deliberately do not mark articles processed. `--no-enrich` additionally skips both LLM stages and discovery, so that option cannot evaluate Luna's editorial decisions.

Rollback in the current PowerShell session:

```powershell
$env:ARTICLE_SELECTION_MODE = "deterministic"
```

**Recommendation:** enable Luna by default after the controlled dry run shows complete classifications (or explicitly reviewed failures), sensible regions and overflow, acceptable spend/latency, and an editor approves the retained/rejected examples. Until that review, keep the shipped default deterministic. The earlier measured recall improvement supports proceeding; offline tests establish integration behavior, not fresh editorial accuracy or elimination of threshold-edge model variability.

Remaining limits: sparse or repeated-title snippets; model mistakes and prompt injection cannot be eliminated by instructions; uncertain metadata may remain deferred under the assessment budget; unresolved geographic outputs require review; retry/split recovery can increase classifier requests; the enrichment attempt budget is not a hard billing cap; two-pass allocation is a simple heuristic; existing title-based event similarity still misses differently worded duplicates or can overmerge similar headlines. No new classifier accuracy claim is made without a real post-integration dry run.

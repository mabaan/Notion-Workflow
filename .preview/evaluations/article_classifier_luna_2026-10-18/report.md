# SOMA MATER: Luna classification and enrichment comparison - 18 October 2026

**Recommendation: use GPT-6 Luna for further controlled evaluation; NO-GO for replacing production selection on this evidence alone.** Luna fixes the earlier cheap-model geography errors and matches the existing screen on binary precision/recall. After both screens use the same real Luna enrichment, they produce identical qualified candidates and identical final selections. The remaining clear-positive miss occurs in enrichment, not in either screen.

## What was compared

The user clarified that Luna should be used for classification **and enrichment in both selection methods**. The deterministic screen itself does not use a model. This run compares:

- Existing deterministic screen -> real GPT-6 Luna enrichment -> unchanged in-memory queue selection.
- GPT-6 Luna classifier (100-article ceiling) -> the same real Luna enrichment scores -> the same queue selection.
- A consistency variant with the same Luna classifier split into 18/17 -> the same enrichment scores/selection.

All actual API responses in this rerun report **gpt-6-luna**, medium reasoning, standard/default service tier. No GPT-4.1 requests were made. No production behavior/defaults, prompts, thresholds, quotas, scores, publisher caps, schemas or persistent ingestion state were changed. No Notion client, fresh collection, article retrieval, external research or full ingestion was run.

## Dataset and fairness

The original benchmark/reference is unchanged: **35 records: 25 dated historical primary articles, 3 title-only supplements and 7 user-described scenarios**. Only 10 have original RSS descriptions. Missing snippets remain empty and missing dates remain null; no metadata was invented. Primary labels comprise **5 clear positives, 11 clear negatives and 9 borderline cases**. These are provisional analyst labels frozen before the previous model experiment, not independently human-adjudicated truth. Borderlines are excluded from binary precision/recall. The convenience sample is too small for population-quality claims.

Both screens see the same saved metadata. Historical freshness uses 2026-10-16 23:59:59 UTC. Missing-date supplements and scenario descriptions remain diagnostic only and do not enter the main enrichment comparison. They are not counted as deterministic editorial false negatives. Original fixture placeholder URLs remain visible; no URL content was fetched.

For fairness, each distinct article retained by any screen is enriched **once**, using the original identical title/snippet/publisher/date/source hints. These scores are cached by stable ID and reused by all paths. Screen-assigned regions and classifier scores are not passed into the shared enrichment. Thus this isolates screening and routing differences; it is not a byte-for-byte production replay of the region tags supplied to enrichment. There are 18 unique enrichment calls instead of 40 separate calls across all three paths. Neither generated enrichment nor prior selections replace the frozen reference labels.

The existing enrichment prompt and parser are used without editing. Evaluation-only limits add 4,096 maximum completion tokens including reasoning, 120-second request timeout, default service tier and zero SDK retries. Registered-source relevance threshold remains **4**, unregistered-source threshold **5**. Relevance and significance remain separate. Queue scoring uses the existing **70/20/10** function. Existing quotas Global/UAE/KSA/Egypt = **3/4/3/2**, publisher cap **2**, run limit **12**, and existing event suppression run offline against an empty historical weekly state.

## Screening results

| Screen | Retained / 25 | Precision | Recall | Clear FP | Clear FN | Region accuracy / 14 |
|---|---:|---:|---:|---:|---:|---:|
| deterministic | 13 | 71.4% | 100.0% | 2 | 0 | 92.9% |
| luna-100 | 14 | 71.4% | 100.0% | 2 | 0 | 100.0% |
| luna-repartitioned | 13 | 71.4% | 100.0% | 2 | 0 | 100.0% |

Precision is TP/(TP+FP) on the 16 clear-reference articles; region accuracy checks the 14 mission-positive/borderline cases with explicit acceptable reference assignments, whether retained or not. It is not accuracy of final selected articles. Gate-only deterministic results and every input/classification/rationale are in [comparison.md](comparison.md).

Unlike the previous mini/nano run, both Luna classifier configurations route both Hormuz food stories to **Global** and ACWA/Mongolia to **Out of Scope/Unclear**, matching the reference. The deterministic screen still routes Mongolia to KSA. Both Luna runs correctly recognize the diagnostic Sharjah investment (UAE), Egypt battery assembly (Egypt), and West Bank geography (Global), and reject the routine Saudi weather scenario and explicitly foreign-local water scenario. These diagnostics lack sufficient saved metadata for a production-eligible enrichment replay.

False positives differ: the deterministic screen retains the Syrian petroleum letter-of-credit and Saudi hydrocarbon-export commentary. Luna-100 instead retains battery-definition commentary and generic Gulf project spending as Borderline. The repartitioned Luna retains the hydrocarbon commentary and Gulf spending. All five clear positives survive each screen.

## Outcomes after the same Luna enrichment

| Path | Logical enrichment inputs | Qualified | Precision after relevance threshold | Recall after relevance threshold | Final selected | Final precision | Final reference coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| deterministic -> Luna enrichment | 13 | 4 | 100.0% | 80.0% | 3 | 100.0% | 60.0% |
| luna-100 -> Luna enrichment | 14 | 4 | 100.0% | 80.0% | 3 | 100.0% | 60.0% |
| luna-repartitioned -> Luna enrichment | 13 | 4 | 100.0% | 80.0% | 3 | 100.0% | 60.0% |

**All three paths qualify the same four stories:** Iraq/ACWA solar, Qatar renewables, observed Hormuz harvest impacts, and the Hormuz fertilizer-plan warning. They retain no clear negatives after enrichment.

**The missed valuable article is Egypt's National Veal Project.** Both screens retain it, but the shared Luna enrichment gives relevance **3/5**, significance **2/5**, so it fails the unchanged registered-source threshold of 4. Its explanation acknowledges livestock/agri-food relevance but cites missing scale and impact. Under the provisional reference this is a downstream false negative and suggests relevance may be penalized for uncertainty that should primarily affect significance. No threshold or prompt was adjusted to conceal the miss. Full article evidence was unavailable, so this metadata-only result does not establish how production full-text enrichment would score it.

**All paths choose the same three final stories**, in ranked score order:

| Article | Region | Enrichment relevance | Significance | Queue score |
|---|---|---:|---:|---:|
| Iraq in talks with Saudi’s Acwa to increase solar capacity - Arabian Gulf Business Insight &#124; AGBI | Global | 5 | 2 | 88.00 |
| Qatar’s renewable energy share set to more than double by 2035 - Fast Company Middle East | Global | 5 | 3 | 87.00 |
| Hormuz shipping disruption is starting to hit harvests, UN agency says - Arab News | Global | 4 | 3 | 76.00 |

The fertilizer-plan warning qualifies but does not fit the **three-story Global quota** after the higher-scoring Iraq and Qatar stories and newer harvest-impact story. This is a quota exclusion, separate from the Veal enrichment rejection. Final coverage is 3/5 (60%), whereas editorial qualification recall is 4/5 (80%). No same-event merge suppresses the two distinct Hormuz developments. All final selected regions are correct under the reference; the shared-score final pool happens to eliminate the baseline's earlier Mongolia routing error.

## Every dated primary article

Cells show screening and downstream outcome. A shared enrichment score exists only for the 18-article union. R/S/Q = enrichment relevance / significance / 70-20-10 queue score. Full generated summaries, reasons and evidence points are in `enrichment/outcomes.json`.

| ID / headline | Reference | Shared R/S/Q | Deterministic -> Luna | Luna-100 -> Luna | Luna-18/17 -> Luna |
|---|---|---|---|---|---|
| rss-00: Syria’s central bank issues first letter of credit in 14 years | Irrelevant | 2/3/50.00 | below unchanged relevance threshold | screen rejected | screen rejected |
| rss-01: Acwa to consider solar and wind projects in Mongolia | Borderline | 2/3/50.00 | below unchanged relevance threshold | below unchanged relevance threshold | screen rejected |
| rss-02: QatarEnergy reveals steep fall in profit and revenue | Borderline | 2/4/54.00 | below unchanged relevance threshold | screen rejected | below unchanged relevance threshold |
| rss-03: Adia backs IPO of India’s Zetwerk as anchor investor | Irrelevant | not requested | screen rejected | screen rejected | screen rejected |
| rss-04: Mubadala’s GlobalFoundries lands $21bn US chip project | Irrelevant | not requested | screen rejected | screen rejected | screen rejected |
| rss-05: Qatar companies get grant to offset higher shipping costs | Borderline | 3/3/64.00 | screen rejected | screen rejected | below unchanged relevance threshold |
| rss-06: US plans to ease sanctions on shadow fleet | Irrelevant | not requested | screen rejected | screen rejected | screen rejected |
| rss-07: Demand destruction: an indelicate forecast | Irrelevant | 2/2/46.00 | below unchanged relevance threshold | screen rejected | below unchanged relevance threshold |
| rss-08: State spending cushions Gulf projects from war | Irrelevant | 2/3/50.00 | screen rejected | below unchanged relevance threshold | below unchanged relevance threshold |
| rss-09: Two vessels sink off Oman as Hormuz attacks intensify | Borderline | 2/4/54.00 | screen rejected | below unchanged relevance threshold | below unchanged relevance threshold |
| oct16-negation: Not AI. Not energy. Not water. Mohammed bin Rashid says the currency of the future is trust - Gulf News | Irrelevant | not requested | screen rejected | screen rejected | screen rejected |
| oct16-battery_definition: Your battery may not be a battery - Nature | Irrelevant | 2/1/42.00 | screen rejected | below unchanged relevance threshold | screen rejected |
| oct16-battery_science: Evidence for multi-Li+ clustering in lithium-ion battery electrolytes - Nature | Borderline | 3/2/60.00 | screen rejected | below unchanged relevance threshold | screen rejected |
| oct16-crypto: Standard Chartered licensed to launch crypto trading in UAE - Arabian Gulf Business Insight &#124; AGBI | Irrelevant | not requested | screen rejected | screen rejected | screen rejected |
| oct16-flights: Flying from the UAE this weekend? Saudi flights face major disruption as cancellations mount - Gulf News | Irrelevant | not requested | screen rejected | screen rejected | screen rejected |
| oct16-commission: Saudi Arabia Wins Two International Commission on Irrigation and Drainage Awards in France - وكالة الأنباء السعودية | Borderline | 3/2/57.00 | below unchanged relevance threshold | below unchanged relevance threshold | below unchanged relevance threshold |
| oct16-veal: Egypt's minister approves new funding for National Veal Project - Zawya | Relevant | 3/2/56.00 | below unchanged relevance threshold | below unchanged relevance threshold | below unchanged relevance threshold |
| oct16-gerd: GERD Explained 2026: Ethiopia, Egypt and the Nile Dam Dispute | Borderline | 4/2/64.00 | below unchanged relevance threshold | below unchanged relevance threshold | below unchanged relevance threshold |
| oct16-harvests: Hormuz shipping disruption is starting to hit harvests, UN agency says - Arab News | Relevant | 4/3/76.00 | final selected | final selected | final selected |
| oct16-iraq: Iraq in talks with Saudi’s Acwa to increase solar capacity - Arabian Gulf Business Insight &#124; AGBI | Relevant | 5/2/88.00 | final selected | final selected | final selected |
| oct16-libya: Flooded streets, damage in Libya as heavy rains paralyze capital - Arab News | Borderline | 3/2/58.00 | below unchanged relevance threshold | below unchanged relevance threshold | below unchanged relevance threshold |
| oct16-qatar: Qatar’s renewable energy share set to more than double by 2035 - Fast Company Middle East | Relevant | 5/3/87.00 | final selected | final selected | final selected |
| oct15-istanbul: Heavy rain and flooding in Istanbul forces closure of schools - Arab News | Irrelevant | not requested | screen rejected | screen rejected | screen rejected |
| oct15-hormuz: Failure to activate Hormuz fertilizer plan could trigger food crisis, UN official says - Arab News | Relevant | 4/3/76.00 | qualified; quota exclusion | qualified; quota exclusion | qualified; quota exclusion |
| oct15-bahrain: Bahraini fund to invest in power grids across US and Europe - Arabian Gulf Business Insight &#124; AGBI | Borderline | 2/2/46.00 | below unchanged relevance threshold | below unchanged relevance threshold | screen rejected |

## Completeness, consistency and batch recommendation

All 35 articles have exactly one validated result in each classifier run: 35/35 and 35/35, with no missing, unknown or duplicate IDs and no recovery splits. All 18 distinct enrichments completed and parsed successfully; no operational failure was treated as an editorial rejection.

- decision: 28/35 agreement; changed IDs: rss-01, rss-02, rss-05, rss-07, oct16-battery_definition, oct16-battery_science, oct15-bahrain.
- assigned_region: 31/35 agreement; changed IDs: rss-06, oct16-battery_definition, oct16-battery_science, oct15-istanbul.
- relevance_score: 26/35 agreement; changed IDs: rss-01, rss-02, rss-05, rss-07, rss-09, oct16-battery_definition, oct16-battery_science, oct16-iraq, oct16-libya.
- primary_mission_topic: 31/35 agreement; changed IDs: oct16-battery_definition, oct16-battery_science, oct16-libya, diagnostic-landscape.

All seven decision changes change retention eligibility: the Mongolia proposal changes Borderline to Irrelevant, Qatar LNG Irrelevant to Borderline, Qatar logistics Irrelevant to Borderline, hydrocarbon commentary Irrelevant to Borderline, battery-definition commentary Borderline to Irrelevant, electrolyte research Borderline to Irrelevant, and Bahrain-grid investment Borderline to Irrelevant (with relevance still 2). All five clear positives are retained consistently and shared enrichment makes the qualified/final sets identical. Borderline scientific/foreign-project recall remains fragile. A repeat call and changed batch composition are confounded, so instability cannot be attributed to batch size alone.

**Batch recommendation:** keep the configured ceiling of 100 for the next controlled trial; no output-completeness problem justified switching to 50 here. The actual requests contained **35, then 18 and 17** articles. No full 50- or 100-article batch was tested, so neither throughput nor superior quality at those sizes is established. Smaller batches did not change final outcomes in this sample.

## Tokens, cost and latency

| Phase | Actual requests | Input tokens | Output tokens (including reasoning) | Total tokens | Estimated USD | Wall seconds |
|---|---:|---:|---:|---:|---:|---:|
| Classification (35 + 18/17) | 3 | 9332 | 9205 | 18537 | 0.00576878 | 95.06 |
| Shared enrichment (18 distinct IDs) | 18 | 21209 | 9691 | 30900 | 0.00749528 | 126.46 |

**Combined:** 21 requests, **49,437 tokens**, estimated **US$0.01326405**, **221.52s** classifier-plus-enrichment wall time. All responses report gpt-6-luna/default tier, with known usage; no unreported-cost requests. Per-method logical calls would be 13 enrichments for the baseline, 1 classifier + 14 enrichments for Luna-100, and 2 classifier + 13 enrichments for the consistency variant. Physical enrichment calls were shared, so those logical counts must not be summed as actual charges. Cache reuse/order in this experiment is not a production cost forecast.

Official OpenAI documentation checked on 18 October 2026 confirms [GPT-6 Luna capabilities and prices](https://developers.openai.com/api/docs/models/gpt-6-luna): $0.10 per million ordinary input tokens, $0.01 cached input, $0.125 cache writes and $0.50 output; short-context Standard/default processing. The ledger uses reported cached/write token counts and counts reasoning inside completion tokens. [Cache-write pricing](https://developers.openai.com/api/docs/guides/prompt-caching) replaces ordinary input pricing, rather than adding to it. No Batch/Flex discount, regional surcharge or tax is assumed. These are estimates, not invoices. The model supports strict structured output, 1,050,000 context tokens and 128,000 output tokens; the evaluation caps are much smaller.

The classifier phase retained its announced caps of 6 requests, 160,000 reserved tokens and $0.25. After the user explicitly requested enrichment in both paths, enrichment was announced at at most 25 additional requests and 320,000 reserved tokens, while preserving a **$0.25 combined** reserved-cost ceiling. Enrichment also has a $0.20 phase ceiling. The combined request/token ceilings are 31 and 480,000, conservatively above actual use.

Actual reservations consumed: **293,877 tokens**, **US$0.08281463**; unused reservations were never refunded. The guard journals/reserves before sending; all attempts and body-read latency are recorded. No additional calls were made after completing the fixed sample. Standalone baseline deterministic latency was 0.0924s and used no API tokens.

## Decision and remaining limits

**Use GPT-6 Luna for subsequent classifier evaluations.** It is substantially more faithful to the mission and geography instructions than the previously tested GPT-4.1 mini/nano. The earlier weak-model classifier-only precision/region results should not be generalized to Luna.

**NO-GO for replacing production selection yet; GO for a larger read-only Luna comparison.** This small frozen sample establishes technical completeness and better preliminary geography, but provides no improvement in clear-positive screening recall, no improvement in final qualified/selected sets, and an important shared enrichment miss. Investigate the relevance-versus-significance handling of sparse agricultural investment metadata in a separate focused step, and independently adjudicate more positive/negative and borderline cases. Do not lower thresholds or modify quotas based on this evaluation.

Limitations: just five clear positives; only ten original descriptions; most fixture URLs are placeholders; no full text; no independently human-reviewed labels; selection-biased convenience sample; missing-date UAE stories and generic Saudi/landscape/water scenarios are diagnostics only; no strong dated UAE/KSA positive cohort for final recall; no real 50/100 batch load test or repeated identical-batch stability estimate; empty historical weekly state; enrichment parser/rubric remain existing production code; shared neutral source-hint enrichment isolates selection but differs from production-assigned region tags. The benchmark measures offline qualification/allocation, not actual editor approval or live Notion outcomes.

## Artifacts and reproduction

- [All 35 inputs, classifications, reference/model rationales and screening ranks](comparison.md); frozen metadata/reference `snapshot_reference.json`; primary metrics `metrics.json`.
- `luna-100.json`, `luna-repartitioned.json`: outcomes, actual model, usage and classifier parameters. `manifest.json`, `prompt.txt`, `requests/`, `network_ledger.json`: frozen inputs/prompt hashes and sanitized requests/responses without headers/credentials.
- `enrichment/manifest.json`, `enrichment/article_enrichment.txt`, `enrichment/outcomes.json`, `enrichment/comparison.json`, `enrichment/requests/`, `enrichment/network_ledger.json`: shared enrichment and exact qualification/final ranking/constraint outcomes.
- `usage_summary.json`: combined usage, budget/state checks and reproduction-script hashes.
- Classifier rerun (new directory required): `.venv/Scripts/python.exe scripts/evaluate_article_classifier.py --live --model gpt-6-luna --output .preview/evaluations/NEW_RUN`.
- Enrich both paths using cached union IDs: `.venv/Scripts/python.exe -m scripts.evaluate_enriched_selection --live --source .preview/evaluations/NEW_RUN`. Omit `--live` to replay captured outcomes offline. Existing phase manifests prevent accidental repeated spending.
- Offline classifier comparison rerender: `.venv/Scripts/python.exe scripts/evaluate_article_classifier.py --report-only --output .preview/evaluations/article_classifier_luna_2026-10-18`.
- Exact frozen reference/prompt and persistent `.local_state` hashes verified unchanged after both phases and tests. No Notion calls or ingestion state writes.

## Files changed for this rerun

- `src/research_automation/clients/article_classifier.py`: verified Luna model limits and medium reasoning; no default/production integration change.
- `scripts/evaluate_article_classifier.py`: requested-model option for both configurations, general outcome reporting, and Luna cache-write-aware accounting/budgeting; singleton enrichment ID mapping.
- `scripts/evaluate_enriched_selection.py`: new bounded read-only shared-enrichment comparison and offline replay.
- `tests/test_article_classifier.py`, `tests/test_classifier_evaluation.py`: Luna parameter/pricing/plan and plain-text enrichment ledger coverage.
- `tests/test_enriched_selection_evaluation.py`: new shared-score/threshold/queue-weight/unclear-region/failure tests.
- `docs/article_classifier.md`: Luna capabilities, rerun instructions, budgets and shared-enrichment method.
- `.preview/evaluations/article_classifier_luna_2026-10-18/`: all new experiment/report artifacts. The previous mini/nano experiment is preserved.

Validation: **323 offline tests passed; `git diff --check` passed**. No new dependency or production keyword/prompt/threshold changes.

# SOMA MATER: expanded Luna evaluation - 19 October 2026

**GO for a controlled shadow-integration step using Luna and batches of 100. Production replacement remains NO-GO pending full-pool allocation and editor review.** This larger sample demonstrates recovery of real useful articles rejected by the current keyword screen. It also demonstrates marginal-decision variability and continued final-allocation constraints. No production behavior was changed.

## New evidence and fixed design

- 100 new collected article metadata records, with no exact normalized-title or URL overlap with the original benchmark. The original 35-record controls/reference remain unchanged.
- 70 publisher-balanced broad-feed articles plus 30 explicitly marked mission-focused articles. The latter were deliberately oversampled for recall testing. This is not a population-representative precision estimate.
- Provisional analyst reference labels, frozen before every new model call: 21 Relevant, 63 Irrelevant, 16 Borderline. Independent human adjudication remains outstanding. Models never received these labels.
- A fixed 20-article paired-enrichment panel was selected before classification: 12 clear positives, four clear negatives, four borderlines. All 20 were enriched even if a screen rejected them, to diagnose lost opportunities; the same generated scores were then reused by both selection paths.
- Two identical 100-article calls, the same 100 split into 50/50, a repeat of the original 35-record classifier request, and four identical new Veal enrichments. All calls used gpt-6-luna, medium reasoning. No prompt, threshold, quota, publisher-cap or 70/20/10 scoring changes. Repeats are measurements, not a new voting stage.

## Collection, provenance and sampling limits

One bounded read-only Source Registry query supplied publisher feed URLs, geographic hints and source-quality values; source records/status fields were never updated. Thirteen read-only Google News RSS requests captured 1,300 metadata rows: eight existing broad publisher feeds (800), four mission-focused evaluation searches (400), and an Egypt-focused evaluation search (100). No full articles or live ingestion were run. Every request returned HTTP 200; the exact RSS bytes and queries are saved under `feeds/`, `sources.json`, `collection_http.json`, `targeted_http.json` and per-record provenance. No Notion page IDs or credentials are included in outputs.

The broad-feed pool had 546 unique objective-eligible records after excluding 238 stale items and 16 original-benchmark overlaps. A stable URL-hash/publisher-round-robin sample supplied 70 records; the separate mission cohort supplied 30 reviewed real headlines. Mission-focused RSS queries were evaluation sampling only, not production editorial filters. All 100 pass shared objective URL/title/date/freshness checks at 2026-10-19 00:00 UTC. Historical seen-state exclusions are not applied to this read-only evaluation. Google News URLs were preserved without resolving/fetching full articles.

RSS descriptions largely repeat the headline and publisher; they are genuine returned descriptions, not invented abstracts or previous LLM summaries. This remains a sparse-metadata experiment. Broad-feed records contain no reference-positive stories, so recall cannot be estimated on that 70-record stratum. Recall evidence comes from the deliberately mission-rich cohort; generalizing its prevalence to routine ingestion would be incorrect. Both cohorts remain visible in `metrics.json`.

## Full 100-article screening results

| Method | Retained | TP / 21 | Clear FP / 63 | Clear FN | Precision | Recall | Region correct / 37 |
|---|---:|---:|---:|---:|---:|---:|---:|
| deterministic | 19 | 11 | 4 | 10 | 73.3% | 52.4% | 29/37 |
| deterministic_gate | 25 | 15 | 5 | 6 | 75.0% | 71.4% | 29/37 |
| fresh100-a | 44 | 20 | 9 | 1 | 69.0% | 95.2% | 36/37 |
| fresh100-b | 36 | 20 | 4 | 1 | 83.3% | 95.2% | 36/37 |
| fresh50 | 39 | 20 | 5 | 1 | 80.0% | 95.2% | 36/37 |

Precision/recall use only the 84 clear-reference articles; Borderline is tracked separately. Retention means Relevant or Borderline. Region accuracy checks all 37 positive/borderline cases with an allowed reference assignment, whether retained or rejected. Ambiguous cases can have explicitly permitted alternative regions, so high assignment accuracy does not imply quota-stable routing.

**Gate versus allocation:** the old keyword/geography gate admits 15/21 positives. Its unchanged regional shortlist ceiling admits 11/21. Luna admits 20/21 in all three configurations. Thus the observed gain is not explained only by removing the shortlist ceiling: Luna also recovers articles the old editorial gate never admits. Raw Luna retention (36-44 articles) is not an implementation of a new bounded production shortlist.

Known valuable developments rejected by the old gate include:

- Silal Group expands blueberry production in the UAE through partnership with IQ Berries - Zawya: no company-topic match.
- Sepco secures 500MW/2,000MWh Saudi BESS project contract - Zawya: no company-topic match.
- Qatar targets sustainable food production as self-sufficiency reaches 99% for fresh poultry and dairy - Zawya: no company-topic match.
- EnergyX signs binding $2 billion lithium supply deal with Trafigura - Reuters: no company-topic match.
- China proposes export controls on solar-manufacturing technologies - Reuters: outside geographic mandate.
- France, Germany strike deal on car emissions and UK special status - Reuters: outside geographic mandate.

All three Luna runs reject one provisional reference-positive case: the France/Germany car-emissions and UK-status agreement. They treat it as outside the regional mandate. Its systemic international-policy relevance needs explicit editor adjudication; the reference was not changed after observing the disagreement.

Luna retains more marginal articles in the first full-batch run: 9 clear negatives versus 4 in the existing shortlist. The second identical run retains 4; the 50/50 run retains 5. These mostly concern conventional oil, generic conflict/infrastructure, landscapes, or speculative cyber effects. Higher recall therefore does not guarantee consistently higher screening precision.

## Paired enrichment: 20 fixed cases

Both paths use exactly the same real Luna enrichment per panel ID. The reference does not change based on these scores. The existing relevance thresholds remain 4 for registered sources and 5 for unregistered; all new panel sources are registered. Existing significance and queue-score functions are reused.

| Path | Reference positives qualified / 12 | Clear negatives qualified / 4 | Borderlines qualified / 4 | Precision | Recall | Panel final winners |
|---|---:|---:|---:|---:|---:|---:|
| deterministic -> shared Luna | 8 | 0 | 1 | 100.0% | 66.7% | 6 |
| fresh100-a -> shared Luna | 12 | 0 | 1 | 100.0% | 100.0% | 6 |
| fresh100-b -> shared Luna | 12 | 0 | 1 | 100.0% | 100.0% | 6 |
| fresh50 -> shared Luna | 12 | 0 | 1 | 100.0% | 100.0% | 6 |

**Luna recovers four additional qualified reference positives in this panel.** Three are hard keyword-gate misses, and one is a shortlist-ceiling deferral:

| Article | Old reason | Enrichment relevance | Significance |
|---|---|---:|---:|
| Silal Group expands blueberry production in the UAE through partnership with IQ Berries - Zawya | no company-topic match | 4 | 2 |
| Sepco secures 500MW/2,000MWh Saudi BESS project contract - Zawya | no company-topic match | 5 | 4 |
| Qatar targets sustainable food production as self-sufficiency reaches 99% for fresh poultry and dairy - Zawya | no company-topic match | 5 | 3 |
| Iraq's North Oil Company targets zero gas flaring by end-2027 - Zawya | shortlist ceiling | 4 | 3 |

**Final allocation is still constrained.** Each panel path selects six articles: five clear positives plus the borderline University of Tabuk renewable-research grant. Each exhausts the same three publishers at two stories each (ZAWYA, Gulf News and Saudi Press Agency). The panel is heavily concentrated in these publishers; it cannot establish production-wide final recall. Final positive coverage is therefore 5/12 in every path despite the larger qualified Luna pool.

The actual final titles differ. For example, Luna can select UAE blueberry production where the old pool selects Morocco solar. The Egypt-backed Nile Basin financing story changes between Egypt and Global across Luna calls, both allowed by the provisional reference; this changes which quota slots compete for the limited ZAWYA places. High-scoring Saudi storage is qualified but may still be crowded out by the existing allocation priorities/publisher cap. The existing constraint-count dictionary does not count every dynamic publisher-cap omission, so it is not presented as a complete exclusion audit.

Only the fixed 20-panel enrichments were run. These six-winner sets are panel-only sensitivity results, not predictions for enrichment/allocation of the full 100-article pool or the actual weekly Notion queue. No quota, source cap or selection algorithm was changed.

## Stability and batch size

| Comparison | Decision agreement | Retention agreement | Region agreement | Relevance-score agreement |
|---|---:|---:|---:|---:|
| same_batch_repeat | 88/100 | 90/100 | 95/100 | 78/100 |
| 100_vs_50 | 90/100 | 91/100 | 89/100 | 84/100 |
| historical_same_batch_repeat | 34/35 | 34/35 | 32/35 | 30/35 |

The two full 100-article requests have byte-identical recorded bodies. Their different outputs therefore demonstrate observed generative variability under identical recorded inputs/parameters. All 21 reference-positive retention decisions agree across the two full batches (20 retained, one rejected). Most retention instability concerns weak/borderline material. The 100-versus-50 comparison includes both a new stochastic call and changed batch context, so it does not isolate a causal batch-size effect.

**Recommendation: retain the default ceiling of 100.** Full 100 batches are now empirically validated twice, alongside two complete 50-article batches. There were no output/ID-validation failures, recovery splits or missing classifications. The full runs took 72.39s and 73.29s; 50/50 took 110.04s and used more total tokens. Recall was identical. The 50/50 precision result lies within the two full-batch results, so there is no demonstrated editorial-quality advantage for 50. This is a small experiment, not a throughput SLA.

## Veal enrichment was not a stable failure

Relevance across the previous request and four new identical reruns: **[3, 4, 4, 4, 4]**. Significance: **[2, 2, 2, 2, 2]**. All four new requests match the previous recorded request exactly, including prompt, metadata, reasoning and output cap. Four of five calls clear the unchanged threshold of 4; none failed technically. The earlier 3/5 result was not reproduced in the four new calls. It should not be treated as a deterministic rejection rule or a reliable estimate of a miss rate. The recorded model alias remains gpt-6-luna; an unversioned alias and backend nondeterminism limit causal attribution across days.

No majority vote, threshold relaxation or prompt adjustment was introduced. Significance stayed at 2, which reflects limited evidence about scale. Relevance crossed the admission threshold despite identical metadata, so near-threshold stories remain worth targeted editorial review.

## API usage, budget and safeguards

| Stage | Requests | Prompt tokens | Completion tokens incl. reasoning | Total tokens | Wall seconds |
|---|---:|---:|---:|---:|---:|
| fresh100-a | 1 | 18340 | 10099 | 28439 | 72.39 |
| fresh100-b | 1 | 18340 | 10515 | 28855 | 73.29 |
| fresh50 | 2 | 19138 | 13867 | 33005 | 110.04 |
| historical-repeat | 1 | 4267 | 4016 | 8283 | 33.19 |
| 20 paired enrichments + 4 Veal repeats | 24 | 31183 | 12225 | 43408 | 118.26 |

**Actual total: 29 API requests, 141,990 provider-reported tokens, estimated US$0.03426492, 407.16s model-run wall time.** All responses report gpt-6-luna and known usage. No refusals, malformed outputs, retries, local budget denials or unresolved outcomes occurred. There are 335 validated classification outcomes across 135 distinct metadata records (100 new plus 35 original controls), 20 new paired enrichments and 4 new Veal repeats. None is a Notion write.

The announced shared ceilings were 30 requests, 700,000 conservatively reserved tokens and US$0.25 reserved estimated cost. Offline preflight predicted exactly 29 requests, 615,670 reserved tokens and US$0.16911875; actual reservations match. Every network send was reserved and journaled in advance, SDK retries were disabled, and unused reservations were not refunded. The spare request was not used. Budget estimates are not provider invoice guarantees.

Official [GPT-6 Luna documentation](https://developers.openai.com/api/docs/models/gpt-6-luna) was rechecked on 19 October 2026: Standard short-context rates per million tokens are $0.10 ordinary input, $0.01 cached input, $0.125 cache writes and $0.50 output. The ledger uses actual cached/write counts and completion usage, including reasoning. Cache-write pricing replaces ordinary input pricing. No Batch/Flex discount, regional surcharge or tax is assumed. All 29 successful requests/responses are archived without HTTP headers/keys; standard/default service tier is recorded in raw responses.

Persistent ingestion-state hashes match before collection, before model evaluation and after completion. The original benchmark, prompts and current production scoring/routing/selection code were preserved. Source lookup/feed GETs were read-only, and the model runner never constructs a Notion client. No ingestion run, article retrieval or source-status update occurred.

## Decision and next validation boundary

**GO for controlled shadow integration of the independent Luna classifier with a 100-article ceiling and explicit handling of Borderline/failed outcomes.** Unlike the first small benchmark, this sample demonstrates important real keyword-gate misses recovered by the classifier and confirmed by unchanged Luna enrichment. Keep existing human review.

**Production replacement remains NO-GO at this point.** The remaining boundary is concrete: compare the entire retained pool under the actual bounded enrichment allocation and weekly publisher/region state, with editor-adjudicated reference labels. The fixed panel does not validate those full-pool decisions, precision varies across repeated calls, and borderline region choices can alter final allocation. The European emissions-policy scope disagreement and the near-threshold Veal behavior deserve editorial review. No claim of better final newsletter quality is supported by this panel alone.

Limitations: manually chosen mission oversampling; no independent human labels; mainly headline-repeat descriptions; no full-text evidence; a ZAWYA-heavy mission cohort/panel; just two same-batch repeats and one 50/50 comparison; articles rather than independent event clusters as the metric unit; unversioned model alias; no prospective editor-acceptance measurement. Reference labels can be challenged without silently rewriting these captured results.

## Reviewable case files and reproduction

- `snapshot_reference.json`: all 100 inputs, source provenance, cohorts, frozen reference rationale/acceptable regions and fixed panel IDs.
- `article_comparison.csv`: every headline, reference label, old gate/shortlist/routing/rank, all three classifier outcomes and diagnostic rank. Diagnostic screen ranks are not a production allocation or final queue score.
- `fresh100-a.json`, `fresh100-b.json`, `fresh50.json`, `historical-repeat.json`: exact model classifications, justifications, parameters, timing and usage.
- `panel_enrichment.json`, `panel_comparison.json`: generated shared enrichments, unchanged 70/20/10 ranking, threshold outcomes, panel-only final winners and shortages.
- `veal_repeats.json`, `veal_stability.json`, `consistency.json`, `metrics.json`: repeat distributions, changed IDs, aggregate and separate cohort metrics.
- `requests/`, `network_ledger.json`, `preflight.json`, `manifest.json`, `integrity_usage.json`: sanitized exact calls/responses, hard-budget accounting, hashes and state checks.
- `feeds/` plus collection/source JSON: original public RSS bytes and read-only source metadata. Saved inputs suffice for offline replay; another source lookup is unnecessary.
- Offline replay: `.venv/Scripts/python.exe -m scripts.evaluate_luna_followup` (no API calls). An authorized rerun needs `--live`, a fresh output directory with a separately prepared frozen snapshot/reference, and the same hard preflight/transport limits. Existing manifests prevent accidental repeated spending.

## Files changed in this follow-up

- Added `scripts/evaluate_luna_followup.py`: frozen full-batch/repeat experiment, shared enrichment panel, budget preflight and offline analysis.
- Added `tests/test_luna_followup_evaluation.py`: ID-based comparison, retention-versus-label changes, no-network whole-experiment preflight and incomplete-sample rejection.
- Updated `docs/article_classifier.md`: experiment design, replay, caps and panel limitations.
- Added `.preview/evaluations/luna_followup_2026-10-19/` data, manifests, model captures and this report. Earlier experiments remain intact.
- No production code, prompt, schema, threshold, quota, source cap, default model or dependency changes in this follow-up.

Validation: **326 tests passed; `git diff --check` passed.** All announced model requests completed within budget; all reference/prompt/state integrity checks passed.

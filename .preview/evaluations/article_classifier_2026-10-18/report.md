# SOMA MATER classifier evaluation — 18 October 2026

**NO-GO for replacing production deterministic selection.** On the dated reference subset, both LLM models preserve recall but retain more clear negatives and make more region errors. Complete JSON output and low cost do not establish editorial quality.

## Scope and reference

35 frozen records: **25 primary dated historical articles**, **3 title-only supplements**, and **7 user-described scenarios**. Only ten original RSS descriptions survive on this device. Other snippets are empty; missing publication dates are null. The old audit files are unavailable. No fresh feeds, full articles, search, ingestion or Notion calls were used.

The primary set has **5 clear positives, 11 clear negatives and 9 borderline cases**. Reference labels and their rationales were authored before the first API call; previous LLM decisions and generated summaries were excluded. These are provisional analyst judgments for human review, not independently adjudicated ground truth. Borderline cases are excluded from binary precision/recall and reported separately. This small, selected convenience sample is not a population accuracy estimate.

Both methods see exactly the same title, snippet, publisher, date and source hints. Legacy ranking also retains its existing publisher-quality/registration metadata. The model never receives labels, source quality, provenance or previous scores. Historical replay uses **2026-10-16 23:59:59 UTC**, the unchanged 7-day window, and all four quota deficits open. Current processed-state exclusions are deliberately not applied to this retrospective editorial comparison. Fixture placeholder URLs remain explicit; they cannot validate actual URL extraction.

The baseline executes unchanged `_prepare_candidate` and `evaluate_candidate_pool` with enrichment disabled and the existing maximum of 8 per region. The gate-only view isolates keywords/geography from shortlist allocation. No final enrichment, significance or 70/20/10 queue scores are fabricated. LLM retention means **Relevant OR Borderline**; unresolved failures would remain eligible and be reported separately.

## Primary results

| Method | Retained / 25 | Precision | Recall | FP | FN | Borderlines retained / 9 | Region accuracy / 14 |
|---|---:|---:|---:|---:|---:|---:|---:|
| deterministic | 13 | 71.4% | 100.0% | 2 | 0 | 6 | 92.9% |
| deterministic_gate | 15 | 71.4% | 100.0% | 2 | 0 | 8 | 92.9% |
| mini-100 | 22 | 38.5% | 100.0% | 8 | 0 | 9 | 78.6% |
| mini-repartitioned | 22 | 38.5% | 100.0% | 8 | 0 | 9 | 78.6% |
| nano-100 | 19 | 45.5% | 100.0% | 6 | 0 | 8 | 85.7% |

Precision uses only clear positive/negative labels: TP/(TP+FP), excluding retained borderlines. Region accuracy checks all 14 mission-positive/borderline articles with reviewable expected geography, regardless of retention; ambiguous awards/explainers have explicit acceptable alternatives. This is assignment accuracy, not final queue routing accuracy.

**Missed valuable articles:** none of the five primary positives is missed by the current baseline or either model. In particular, the current code already retains Veal, Iraq solar, Qatar renewables and both distinct Hormuz developments. Historical fixture `before` values are not results from this checkout. The benchmark therefore supplies **no demonstrated gain in clear-positive recall**.

The old gate rejects the battery-electrolyte paper (a conditional applied-science candidate); its shortlist ceiling additionally defers Qatar logistics support and the unspecified Hormuz vessel story. Mini preserves all three as potentially relevant. Nano rejects the electrolyte paper, a possible conditional false negative requiring human assessment. None is counted as a proven important miss.

**False positives:** the baseline retains the Syrian petroleum letter-of-credit article and hydrocarbon export commentary. Mini retains these plus the Indian IPO, US semiconductor investment, shadow-fleet oil sanctions, generic Gulf spending, battery-definition commentary and Istanbul school-closure flood story. Nano avoids the latter two but still retains the other six. Mini's statement that unspecified manufacturer logistics aid supports food security is unsupported by the supplied snippet. Its Gulf-spending-to-net-zero bridge is also unsupported.

**Incorrect regions:** ACWA's Mongolia project is Global in every LLM run and KSA in the baseline, rather than the reference's foreign-project Out of Scope/Unclear. Both mini runs put both systemic Hormuz food stories in KSA; the baseline and nano put them in Global. Nano puts the Egyptian Veal funding in Global. MENA participant nationality or publisher hints continue to contaminate model geography.

## Every primary article

R = retained into the legacy enrichment shortlist; X = rejected/deferred. Parentheses show gate/ceiling reasons. Model cells give decision, 1–5 relevance and region. Every model result/rationale is captured in the JSON files.

| ID / headline | Reference | Legacy decision; region | Mini 100 | Mini 18 | Nano 100 |
|---|---|---|---|---|---|
| rss-00: Syria’s central bank issues first letter of credit in 14 years | Irrelevant | R; Global | Relevant 4; Global | Borderline 2; Global | Borderline 3; Global |
| rss-01: Acwa to consider solar and wind projects in Mongolia | Borderline | R; KSA | Relevant 4; Global | Relevant 4; Global | Borderline 3; Global |
| rss-02: QatarEnergy reveals steep fall in profit and revenue | Borderline | R; Global | Relevant 4; Global | Borderline 3; Global | Borderline 3; Global |
| rss-03: Adia backs IPO of India’s Zetwerk as anchor investor | Irrelevant | X (no company-topic match); UAE | Borderline 2; Out of Scope/Unclear | Borderline 2; Global | Borderline 2; Global |
| rss-04: Mubadala’s GlobalFoundries lands $21bn US chip project | Irrelevant | X (no company-topic match); UAE | Borderline 2; Out of Scope/Unclear | Borderline 2; Global | Borderline 3; Global |
| rss-05: Qatar companies get grant to offset higher shipping costs | Borderline | X (shortlist ceiling); Global | Relevant 4; Global | Relevant 4; Global | Borderline 3; Global |
| rss-06: US plans to ease sanctions on shadow fleet | Irrelevant | X (no exact target region); Unclear | Borderline 3; Global | Borderline 3; Global | Borderline 2; Global |
| rss-07: Demand destruction: an indelicate forecast | Irrelevant | R; KSA | Relevant 4; KSA | Relevant 4; KSA | Borderline 2; Global |
| rss-08: State spending cushions Gulf projects from war | Irrelevant | X (no company-topic match); Global | Relevant 4; Global | Relevant 4; Global | Borderline 2; Global |
| rss-09: Two vessels sink off Oman as Hormuz attacks intensify | Borderline | X (shortlist ceiling); Global | Relevant 4; Global | Relevant 4; Global | Borderline 2; Global |
| oct16-negation: Not AI. Not energy. Not water. Mohammed bin Rashid says the currency of the future is trust - Gulf News | Irrelevant | X (no company-topic match); UAE | Irrelevant 1; UAE | Irrelevant 1; UAE | Irrelevant 1; Global |
| oct16-battery_definition: Your battery may not be a battery - Nature | Irrelevant | X (battery coverage without a transition application); Global | Borderline 2; Global | Borderline 2; Global | Irrelevant 1; Global |
| oct16-battery_science: Evidence for multi-Li+ clustering in lithium-ion battery electrolytes - Nature | Borderline | X (battery coverage without a transition application); Global | Borderline 2; Global | Borderline 2; Global | Irrelevant 1; Global |
| oct16-crypto: Standard Chartered licensed to launch crypto trading in UAE - Arabian Gulf Business Insight \| AGBI | Irrelevant | X (consumer finance or passenger travel without a direct mission consequence); UAE | Irrelevant 1; UAE | Irrelevant 1; Out of Scope/Unclear | Irrelevant 1; Global |
| oct16-flights: Flying from the UAE this weekend? Saudi flights face major disruption as cancellations mount - Gulf News | Irrelevant | X (consumer finance or passenger travel without a direct mission consequence); Unclear | Irrelevant 1; UAE | Irrelevant 1; UAE | Irrelevant 1; Global |
| oct16-commission: Saudi Arabia Wins Two International Commission on Irrigation and Drainage Awards in France - وكالة الأنباء السعودية | Borderline | R; KSA | Relevant 4; KSA | Relevant 4; KSA | Borderline 3; KSA |
| oct16-veal: Egypt's minister approves new funding for National Veal Project - Zawya | Relevant | R; Egypt | Relevant 4; Egypt | Relevant 4; Egypt | Borderline 2; Global |
| oct16-gerd: GERD Explained 2026: Ethiopia, Egypt and the Nile Dam Dispute | Borderline | R; Egypt | Relevant 5; Egypt | Relevant 5; Egypt | Relevant 4; Egypt |
| oct16-harvests: Hormuz shipping disruption is starting to hit harvests, UN agency says - Arab News | Relevant | R; Global | Relevant 5; KSA | Relevant 5; KSA | Relevant 4; Global |
| oct16-iraq: Iraq in talks with Saudi’s Acwa to increase solar capacity - Arabian Gulf Business Insight \| AGBI | Relevant | R; Global | Relevant 4; Global | Relevant 4; Global | Relevant 4; Global |
| oct16-libya: Flooded streets, damage in Libya as heavy rains paralyze capital - Arab News | Borderline | R; Global | Borderline 3; Global | Borderline 3; Global | Borderline 2; Global |
| oct16-qatar: Qatar’s renewable energy share set to more than double by 2035 - Fast Company Middle East | Relevant | R; Global | Relevant 4; Global | Relevant 4; Global | Relevant 4; Global |
| oct15-istanbul: Heavy rain and flooding in Istanbul forces closure of schools - Arab News | Irrelevant | X (outside geographic mandate); Unclear | Borderline 3; Out of Scope/Unclear | Borderline 3; Out of Scope/Unclear | Irrelevant 1; Global |
| oct15-hormuz: Failure to activate Hormuz fertilizer plan could trigger food crisis, UN official says - Arab News | Relevant | R; Global | Relevant 5; KSA | Relevant 5; KSA | Relevant 5; Global |
| oct15-bahrain: Bahraini fund to invest in power grids across US and Europe - Arabian Gulf Business Insight \| AGBI | Borderline | R; Global | Borderline 2; Out of Scope/Unclear | Borderline 2; Out of Scope/Unclear | Borderline 2; Global |

## Supplements and scenario probes

These ten records fail shared objective prechecks because publication dates/URLs are unavailable. They are sent directly to the independent classifier solely to expose editorial behavior. They are **excluded from primary precision/recall**; baseline objective exclusion is not an editorial false negative. Sharjah and Egypt battery records were previously saved, so they are not evidence that the old system missed those stories. Missing source hints are not invented to recreate the previous West Bank live misrouting.

| ID / title or explicitly labeled scenario | Reference | Legacy objective exclusion | Mini 100 | Mini 18 | Nano 100 |
|---|---|---|---|---|---|
| saved-sharjah (supplemental): 410,000 m³ of water a day, 35 more years at the ports and 600,000 tonnes of waste capacity: Investing in Sharjah's next growth cycle - Khaleej Times | Relevant | unknown or invalid publication date | Relevant 4; UAE | Relevant 4; UAE | Borderline 2; Global |
| saved-egypt-battery (supplemental): Egypt to get new lithium-ion battery assembly facility - Zawya | Relevant | unknown or invalid publication date | Relevant 4; Egypt | Relevant 4; Egypt | Borderline 3; Egypt |
| user-west-bank (supplemental): 'He irrigated the tree with his blood': West Bank olive farmers set for another deadly harvest | Borderline | invalid URL | Borderline 2; Out of Scope/Unclear | Borderline 3; Global | Irrelevant 1; Out of Scope/Unclear |
| diagnostic-uae-strategy (diagnostic): UAE food-production strategy | Relevant | invalid URL | Relevant 4; UAE | Relevant 4; UAE | Relevant 4; UAE |
| diagnostic-egypt-green (diagnostic): Egypt green industrialisation, subject to novelty and evidence | Borderline | invalid URL | Relevant 4; Egypt | Relevant 4; Egypt | Borderline 3; Egypt |
| diagnostic-saudi-weather (diagnostic): Routine Saudi weather forecasts | Irrelevant | invalid URL | Irrelevant 1; KSA | Irrelevant 1; KSA | Irrelevant 1; KSA |
| diagnostic-landscape (diagnostic): Agricultural landscape descriptions | Irrelevant | invalid URL | Borderline 2; Out of Scope/Unclear | Irrelevant 1; Out of Scope/Unclear | Borderline 2; Global |
| diagnostic-economy (diagnostic): Generic economic news mentioning energy | Irrelevant | invalid URL | Borderline 2; Out of Scope/Unclear | Borderline 2; Out of Scope/Unclear | Borderline 2; Global |
| diagnostic-water-science (diagnostic): Water-related laboratory papers without a demonstrated mission application | Borderline | invalid URL | Borderline 2; Out of Scope/Unclear | Borderline 2; Out of Scope/Unclear | Borderline 2; Global |
| diagnostic-foreign-water (diagnostic): Foreign-local water infrastructure projects without a MENA or systemic bridge | Irrelevant | invalid URL | Irrelevant 1; Out of Scope/Unclear | Irrelevant 1; Out of Scope/Unclear | Irrelevant 1; Out of Scope/Unclear |

Mini recognizes Sharjah water/waste investment and Egypt battery assembly as Relevant 4 with correct geography. Nano leaves both Borderline and assigns Sharjah to Global. West Bank violence remains Borderline with mini (appropriate caution, but region changes from Unclear to Global); nano rejects it. No model should infer broad food-system consequences from that title. Mini gives the generic Egypt green-industrialisation scenario Relevant 4 despite no specific new development; nano's Borderline 3 is more defensible. All runs reject the routine Saudi forecast and the explicitly foreign-local water scenario. These simplified scenarios cannot establish performance on real articles from those categories.

## Candidate ranking

The classifier has no built-in production shortlist ranking. The following **diagnostic-only** ranking sorts retained primary candidates within assigned region by relevance descending, existing publisher quality descending, then publication date descending and ID. It does not implement quotas, publisher caps, significance or final queue scoring. Out of Scope/Unclear remains a separate diagnostic bucket; its candidates are not silently discarded.

| ID | Legacy region / metadata rank | Mini region / diagnostic rank | Nano region / diagnostic rank |
|---|---|---|---|
| rss-00 | Global / 7 | Global / 1 | Global / 5 |
| rss-01 | KSA / 1 | Global / 2 | Global / 6 |
| rss-02 | Global / 8 | Global / 3 | Global / 7 |
| rss-03 | UAE / - | Out of Scope/Unclear / 3 | Global / 11 |
| rss-04 | UAE / - | Out of Scope/Unclear / 4 | Global / 8 |
| rss-05 | Global / 9 | Global / 4 | Global / 9 |
| rss-06 | Unclear / - | Global / 9 | Global / 12 |
| rss-07 | KSA / 3 | KSA / 3 | Global / 13 |
| rss-08 | Global / - | Global / 5 | Global / 14 |
| rss-09 | Global / 10 | Global / 6 | Global / 15 |
| oct16-negation | UAE / - | UAE / - | Global / - |
| oct16-battery_definition | Global / - | Global / 11 | Global / - |
| oct16-battery_science | Global / - | Global / 12 | Global / - |
| oct16-crypto | UAE / - | UAE / - | Global / - |
| oct16-flights | Unclear / - | UAE / - | Global / - |
| oct16-commission | KSA / 2 | KSA / 4 | KSA / 1 |
| oct16-veal | Egypt / 1 | Egypt / 2 | Global / 17 |
| oct16-gerd | Egypt / 2 | Egypt / 1 | Egypt / 1 |
| oct16-harvests | Global / 5 | KSA / 1 | Global / 3 |
| oct16-iraq | Global / 4 | Global / 7 | Global / 2 |
| oct16-libya | Global / 6 | Global / 10 | Global / 16 |
| oct16-qatar | Global / 3 | Global / 8 | Global / 4 |
| oct15-istanbul | Unclear / - | Out of Scope/Unclear / 1 | Global / - |
| oct15-hormuz | Global / 2 | KSA / 2 | Global / 1 |
| oct15-bahrain | Global / 1 | Out of Scope/Unclear / 2 | Global / 10 |

Mini's Hormuz scores of 5 elevate both stories into the KSA bucket despite systemic geography, while the unrelated hydrocarbon commentary scores 4. High relevance for the GERD explainer (5) and irrigation awards (4) establishes topic fit, not novelty or significance. Downstream evidence and significance assessment remain necessary; score rank alone is unsafe for replacing allocation.

## Completeness and batch consistency

- mini-100: 35/35 validated classifications, 0 unresolved; request sizes [35]; 0 recovery splits.
- mini-repartitioned: 35/35 validated classifications, 0 unresolved; request sizes [18, 17]; 0 recovery splits.
- nano-100: 35/35 validated classifications, 0 unresolved; request sizes [35]; 0 recovery splits.
- Mini decision agreement: 32/35; changed IDs: rss-00, rss-02, diagnostic-landscape.
- Mini assigned_region agreement: 31/35; changed IDs: rss-03, rss-04, oct16-crypto, user-west-bank.
- Mini relevance_score agreement: 31/35; changed IDs: rss-00, rss-02, user-west-bank, diagnostic-landscape.
- Mini primary_mission_topic agreement: 30/35; changed IDs: rss-04, rss-05, rss-07, oct16-libya, diagnostic-foreign-water.
- Retention eligibility changes only for the agricultural-landscape scenario; the other decision changes are Relevant↔Borderline. Another stochastic call and changed batch membership are confounded; this is not a controlled proof of a batch-size effect.

**Batch recommendation:** keep 100 as an experimental ceiling, with existing bounded size recovery. The first actual batch was only 35 articles. No coverage or output-validation problem justified switching to 50; two smaller batches (18/17) did not fix the main editorial/geography failures. Neither a full 100 nor a full 50 batch was tested. Validate both with a larger frozen pool before deployment; no production/configuration change is made here.

## API usage, cost and latency

The hard limits were announced before sending requests: **6 network requests, 160,000 conservatively reserved input+output tokens, US$0.25 reserved estimated cost**. The HTTP guard reserves UTF-8 request bytes plus overhead as an input-token upper estimate and maximum completion tokens before every send. Reservations are never refunded; SDK retries are disabled. Local cap denials send nothing and remain unresolved, not editorial rejections. This is a protective estimate, not a provider billing cap.

| Experiment | Actual returned model | Requests | Input tokens | Output tokens | Total tokens | Estimated USD | Wall seconds |
|---|---|---:|---:|---:|---:|---:|---:|
| mini-100 | gpt-4.1-mini-2025-04-14 | 1 | 4270 | 2047 | 6317 | 0.0049832 | 14.99 |
| mini-repartitioned | gpt-4.1-mini-2025-04-14 | 2 | 5071 | 2066 | 7137 | 0.0053340 | 15.18 |
| nano-100 | gpt-4.1-nano-2025-04-14 | 1 | 4270 | 1895 | 6165 | 0.0011850 | 7.14 |

**Total:** 4 network requests; 19,619 provider-reported tokens; **US$0.0115022** estimated cost; 37.31s total classifier wall time. 0 requests have unknown cost. Reserved ceilings consumed: 111,618 tokens and US$0.0831840. No remaining budget was spent merely because it was available.

Pricing assumptions: synchronous standard API, per million tokens: mini $0.40 input / $0.10 cached / $1.60 output; nano $0.10 / $0.025 / $0.40. No Batch API discount, taxes, other service charges, or downstream enrichment-cost savings assumed. Cached input usage is zero in this run. These are estimates, not invoice reconciliation. Official rates/capabilities checked 2026-10-18: [mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano). Both document strict structured output and 32,768 maximum output tokens; no reasoning parameter is sent. Both current pages label the families Deprecated, even though this account successfully returned the listed snapshots.

Legacy local baseline latency: 0.0922s, no API tokens/cost. HTTP timings include response-body receipt; sample size is too small for throughput or p95 claims.

## Recommendation and limits

**NO-GO for production replacement.** Require a human-reviewed larger reference set, fewer incidental-mission retentions, corrected event geography and stable treatment of uncertainty before replacing selection. This benchmark does not demonstrate superior recall and does demonstrate inferior precision. It measures entry to enrichment, not final editor-approved quality or enrichment-call savings.

**Model recommendation:** neither tested model is ready for production editorial screening. Retain **gpt-4.1-mini only as a development comparator** because it recognizes Veal/Sharjah and practical battery infrastructure better; nano's lower price does not compensate for understating these and losing geography. Verify a supported model's lifecycle/capabilities before any later deployment. No default model was changed in this step.

Limitations: 5 clear positives cannot establish recall; most historical descriptions and real URLs are missing; selection-biased saved fixtures overrepresent known issues; user scenarios are not collected news; labels need independent human adjudication; no true 50/100 load or repeated same-batch stability test; no fresh collection or full-text evidence; no final quota/publisher-cap simulation or human editorial acceptance measurement. References can be reviewed in `snapshot_reference.json` before accepting any metric.

## Reproduction and safeguards

- Frozen inputs and provisional reference: `snapshot_reference.json`; tracked source fixture: `tests/fixtures/article_classifier_benchmark.json`.
- Prompt frozen as `prompt.txt`; SHA-256 values, Git HEAD, price assumptions, budget and before/after state hashes: `manifest.json`.
- Raw sanitized request JSON (no headers/keys), successful provider JSON, timing/usage ledger: `requests/`, `network_ledger.json`.
- Offline baseline, model outcomes, metrics and evaluation-only ranks: `deterministic.json`, `mini-100.json`, `mini-repartitioned.json`, `nano-100.json`, `metrics.json`, `diagnostic_ranks.json`, `comparison.md`. The narrative in this report pertains to these specific captured responses; a future run needs its own editorial interpretation.
- Offline comparison-table/metric rerender (does not rewrite this reviewed narrative): `.venv/Scripts/python.exe scripts/evaluate_article_classifier.py --report-only`.
- Offline fresh baseline: `.venv/Scripts/python.exe scripts/evaluate_article_classifier.py --output .preview/evaluations/NEW_NAME`.
- Authorized budgeted rerun only: same command plus `--live`; requires a **new** output directory and uses the same fixed hard budget. Existing manifests prevent accidental repeated spending.
- Optional snapshot rebuild: `scripts/prepare_article_classifier_benchmark.py`; requires the original saved files, including the two local title records. Normal evaluation uses the frozen tracked fixture and needs none of those local files.
- Persistent state unchanged by hash: **True**. Production ingestion, thresholds, quotas, scores, publisher caps, prompts and Notion schema were not changed.
- The sole classifier correctness adjustment allows an explicitly missing date to serialize as null rather than forcing a fabricated timestamp. Its objective preparation adapter still rejects missing publication dates.

Validation: **312 tests passed** in the full offline pytest suite; **`git diff --check` passed**. Unit tests cover fair metric handling, order independence, missing metadata, budget enforcement including retries/unknown costs, and cached-token accounting; all live outcomes also passed the existing strict schema/ID validation.

## Files changed in Step 2

- `scripts/evaluate_article_classifier.py` — new offline baseline, hard-budget live harness, metrics and comparison-table rendering.
- `scripts/prepare_article_classifier_benchmark.py` — new offline provenance-preserving snapshot builder with pre-run provisional reference labels.
- `tests/fixtures/article_classifier_benchmark.json` — new frozen 35-record metadata/reference set.
- `tests/test_classifier_evaluation.py` — new offline evaluation and budget-guard tests.
- `tests/test_article_classifier.py` — unknown-date serialization regression.
- `src/research_automation/models/classification.py` — allow explicit missing publication date and serialize it as null.
- `src/research_automation/clients/article_classifier.py` — accept explicit missing date while still rejecting malformed date values.
- `docs/article_classifier.md` — document missing metadata and controlled evaluation/reproduction.
- `.preview/evaluations/article_classifier_2026-10-18/` — this narrative, generated comparison/ranks/metrics, frozen inputs/prompt/manifest, all three run reports, request/response JSON and network ledger. No credentials or Notion page IDs are included.

Earlier Step 1 changes remain in the workspace. This step did not alter their configuration defaults, enrichment prompt or production ingestion behavior.

# SOMA MATER editorial-scope correction

Completed 19 October 2026. This report covers this request relative to the initial
working tree; earlier uncommitted Luna/Sol work is preserved. No paid API calls,
article collection, Notion writes or ingestion-state mutation occurred.

## Exact classifier prompt changes

The complete before/after patch for both prompts is [prompt_changes.diff](prompt_changes.diff).
Current templates: [classifier](../../../src/research_automation/prompts/article_classification.txt)
and [enrichment](../../../src/research_automation/prompts/article_enrichment.txt).

- Adds primary story type and typed novelty; a current year, action verb or new
  publication date alone cannot establish a new development.
- Clear invalid primary types become Irrelevant; credible unresolved developments
  remain Borderline. The model cannot invent a mission bridge.
- Replaces blanket humanitarian assessment eligibility with the primary-subject
  test. Relief/conflict/malnutrition coverage is excluded when it is the main news;
  actual sector financing, infrastructure or material commercial supply consequences
  can qualify when they are primary.
- Separates concrete sector policy from general politics and sustainability speeches.
- Allows substantial systemic climate/environmental measurements, transition-material
  investigations and consequential new research without requiring a named MENA country.
- Preserves event geography, source hints as hints, untrusted-data boundaries,
  complete ID coverage and recall for sparse but credible metadata. No headline
  blacklist was added.

## Exact enrichment/editorial prompt changes

- Requires the same two fields and makes the final judgment independently from
  supplied article evidence.
- Excludes primary politics/diplomacy, conflict/security, humanitarian relief and
  routine events. Incidental hunger, farmer, water or energy references cannot rescue them.
- Geopolitical context qualifies only when a causal, direct material mission
  consequence is the primary development, using its mission story type.
- Background/commentary needs a distinct substantive recent development,
  novelty=true and an explicit justification identifying the change.
- Important new investigations, measurements and mission-relevant research remain
  eligible; literature reviews need an important new result beyond the review itself.
  Novel laboratory work alone does not establish credible mission application.
- Relevance and significance stay separate. Missing scale/implementation detail
  lowers significance when core financing/capacity is clear; unsupported novelty
  normally has significance 1-2. Repeated wording was tightened so the historical
  evaluation preflight still fits its unchanged budget.

## Structured output and validation

Both ArticleClassification and EnrichedArticle add only `story_type` and
`is_new_development`. The shared enum is:

`development`, `policy_regulation`, `investment_financing`, `infrastructure_project`,
`research_result`, `investigation`, `supply_disruption`, `explainer_background`,
`commentary_opinion`, `politics_diplomacy`, `conflict_security`, `humanitarian_relief`,
`routine_event`, `other`.

Novelty is JSON `true`, JSON `false`, or the string `"unclear"`. Classification
requires both fields in its existing strict schema, using `anyOf` for the novelty
union, and validates locally without coercion. Missing fields, invalid enums,
string `"true"`, integer `1` and null are malformed. ID/cardinality validation,
bounded retries and batch splitting retain their existing behavior. The schema
uses the supported subset in the [official OpenAI structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).

Enrichment retains JSON-object API mode and locally validates the two required
fields before creating EnrichedArticle. Malformed enrichment follows the existing
recorded-failure path without a new repair call. Historical/direct dataclass
constructions default to `other`/`"unclear"`; no old queue items were reclassified.

## Exact final eligibility algorithm

1. Luna keeps Relevant, Borderline and unresolved operational outcomes available
   for existing bounded assessment. Only an explicit Irrelevant decision rejects metadata.
2. Following the existing detailed call, reject novelty `false` for every type.
3. Reject primary politics_diplomacy, conflict_security, humanitarian_relief and
   routine_event even when the event is new. A material mission consequence instead
   uses supply_disruption or the corresponding mission type when it is primary.
4. Reject explainer_background/commentary_opinion unless novelty is explicitly
   `true`. True is necessary, not sufficient: the normal scores/constraints still apply.
5. Other mission types with `"unclear"` novelty continue through existing thresholds.
   The prompt requires an evidence-gap explanation and conservative significance.
   This avoids a new blanket cutoff for uncertain but potentially useful developments.
6. Apply unchanged strict/fallback thresholds, 70/20/10 score, geography, publisher
   cap, coverage, processed/URL exclusions and event constraints. CandidateResult
   defensively applies scope to both tiers; both ingestion evaluation paths record
   scope rejections before qualification.
7. JSON/Markdown audits retain classification_story_type,
   classification_is_new_development, final story_type, final is_new_development,
   editorial_scope_rejection and its decision stage. No Notion property is added.

## Regression examples

These are fixed mocked judgments and parser/eligibility contracts, not measured
live-model accuracy. The detailed prompt/parser/selection cases run with both
Luna and Sol settings. A batch test round-trips all classifier judgments. Invalid
cases deliberately receive high fixed detailed scores to test the scope guard.

| Scenario/title | Primary type | Novelty | Result |
|---|---|---|---|
| GERD Explained 2026: Ethiopia, Egypt and the Nile Dam Dispute | explainer_background | false | Reject |
| Egypt and Ethiopia agree new GERD operating rules | policy_regulation | true | Keep* |
| US ambassador to Israel calls West Bank settler attack on American photojournalist 'terror' | politics_diplomacy | true | Reject |
| Israeli settlers attack European diplomats in West Bank | conflict_security | true | Reject |
| Gaza humanitarian food distribution reaches more families | humanitarian_relief | true | Reject |
| Gaza conflict report mentions hunger among civilians | conflict_security | true | Reject |
| UN says Gaza malnutrition gains fragile as commercial supplies halt | humanitarian_relief | true | Reject |
| Hormuz shipping disruption is starting to hit harvests, UN agency says | supply_disruption | true | Keep* |
| Saudi Reef in Jazan: Over SAR1.2 Billion in Support to Boost Production, Empower Beneficiaries | investment_financing | true | Keep* |
| UAE to grow more food locally under strategy update \| AGBI | policy_regulation | true | Keep* |
| Brazilian Amazon deforestation falls to lowest on record as pivotal vote looms | development | true | Keep* |
| Revealed: VW, Ford and Tesla batteries linked to destructive deforestation of indigenous lands | investigation | true | Keep* |
| The global water conversation is changing | commentary_opinion | false | Reject |
| Regional agricultural festival celebrates another season | routine_event | true | Reject |
| New investment expands desalination capacity | investment_financing | true | Keep* |
| Utility commissions new battery-storage project | infrastructure_project | true | Keep* |
| Political speech praises sustainability without a new measure | politics_diplomacy | false | Reject |
| Government adopts a concrete sustainability regulation | policy_regulation | true | Keep* |
| Literature review surveys familiar membrane research | research_result | false | Reject |
| New field trial establishes practical water-treatment result | research_result | true | Keep* |
| New systemic climate measurement establishes material change | research_result | true | Keep* |
| Agricultural fair announces signed cold-storage financing | investment_financing | true | Keep* |
| Flood destroys irrigation capacity across a major growing region | supply_disruption | true | Keep* |
| Conflict closes fertilizer supply route and cuts agricultural output | supply_disruption | true | Keep* |
| Gaza commercial supply stoppage causes a documented material loss of staple production | supply_disruption | true | Keep* |
| Explainer also reports a distinct new desalination agreement | explainer_background | true | Keep* |
| Commentary reports a substantive newly adopted storage rule | commentary_opinion | true | Keep* |
| Research review establishes an important new quantitative result | research_result | true | Keep* |

*Keep is conditional on the assumed scenario evidence and existing quality, region, cap, event and run-limit constraints. No publisher snippets/text were fabricated. The Gaza humanitarian assessment rejects; a separate primary, documented commercial-production disruption can qualify regardless of geography.

Additional regressions cover Borderline background resolving into a new agreement; laboratory novelty with no mission application failing quality; malformed and typed fields; strict/fallback bypass attempts; unchanged score floors; deterministic rollback scope; scope rejection backfilling; single detailed calls; and dry-run isolation.

## Files changed

- docs/article_classifier.md
- docs/luna_selection.md
- scripts/evaluate_luna_followup.py
- src/research_automation/clients/article_classifier.py
- src/research_automation/clients/llm_client.py
- src/research_automation/models/article.py
- src/research_automation/models/candidate.py
- src/research_automation/models/classification.py
- src/research_automation/models/editorial.py
- src/research_automation/pipeline/candidate_audit.py
- src/research_automation/pipeline/candidate_ranking.py
- src/research_automation/pipeline/luna_selection.py
- src/research_automation/prompts/article_classification.txt
- src/research_automation/prompts/article_enrichment.txt
- tests/test_article_classifier.py
- tests/test_editorial_scope.py
- tests/test_editorial_scoring.py
- tests/test_evidence.py
- tests/test_luna_quality_backfill.py
- tests/test_luna_selection.py
- tests/test_luna_shadow_corrections.py
- tests/test_rss_content.py

22 source/test/documentation files changed. The historical evaluation script changes only its offline dummy response to satisfy the new fields; its request/token/cost ceilings are unchanged. Preview artifacts contain this report, exact diffs, frozen scenarios, test log, protected-file hashes and verification results.

## Verification

- Baseline: 476 passed. Final: 581 passed in 5.85s, full offline suite (105 additional cases). See [pytest.txt](pytest.txt).
- git diff --check: passed (exit 0; no whitespace errors).
- Protected hashes match for .env/.env.example, config, ingestion orchestration, daily runner, final allocator/event logic, retrieval architecture, Notion schema and both local-state JSON files.
- Configured values remain batch 100; enrichment 32/48/8; strict relevance 4/5; fallback relevance/significance 3/3; publisher cap 2; regional targets Global 3/UAE 4/KSA 3/Egypt 2. The score function, retrieval, discovery budgets, caps and event implementation were not changed.
- No paid APIs, live article collection, Notion writes, production-state changes, dependencies, external services or new model stages.

## Remaining ambiguity

Primary subject and substantive novelty remain model judgments. Mixed humanitarian/commercial-supply articles require evidence establishing which development is primary. A newly published investigation can examine older activity, and an explainer can report a new agreement. Offline fixed outputs do not establish future model consistency.

Unclear novelty remains eligible for ordinary mission types if existing thresholds clear; it does not prove novelty. The prompt requires weak evidence to reduce significance. Old saved results remain unknown rather than receiving invented labels. Existing Notion items were not reassessed or removed.

## Next Luna/Sol dry run

This command is provided for the next evaluation and was not executed. It retains the all-publisher scheduling override and existing collection/retrieval flow; dry-run mode writes no Notion pages or ingestion state.

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-sol"
.\.venv\Scripts\python.exe -X utf8 -m scripts.run_daily_ingestion_local --dry-run --all-sources --limit 12
```

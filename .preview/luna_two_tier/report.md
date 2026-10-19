# Two-tier final article selection

Implemented for final Luna selection only. No live API request, publisher fetch,
Notion write or persistent ingestion-state update was performed during this step.
Existing uncommitted work from the preceding steps was preserved.

## Exact algorithm

1. Finish the existing classification and bounded detailed-enrichment process.
   Its stop condition still counts strict winners, so fallback cannot reduce the
   opportunity for later strict candidates. Models, prompts, batch size 100,
   initial budget 32, maximum 48 and backfill batch 8 are unchanged.
2. Run the existing strict-only selector. Registered publishers require final
   relevance 4; unregistered publishers require 5. Preserve its scarce-region-first
   coverage allocation, final-score quality overflow, weekly publisher cap, URL
   exclusion and event matching. These winners are protected, including strict
   overflow winners. If they fill the requested maximum, use no fallback.
3. Otherwise, consider only articles with an existing detailed enrichment and
   final relevance at least 3, final significance at least 3, a registered
   publisher and a valid Global/UAE/KSA/Egypt assignment. Only rejection at the
   strict relevance gate can be relaxed. A processed/duplicate/self-published/
   failed-enrichment or other rejection cannot be relaxed. Explicit publication
   failures, objective-cleanup failures and invalid URLs veto fallback.
4. Carry strict winners' publisher counts, URL identities, regional counts and
   event representatives into fallback allocation. First use eligible fallback
   candidates for remaining regional shortages. Within the chosen region use the
   existing final queue ranking. Then use remaining fallback candidates for
   quality overflow across regions with the same final ranking. Both passes
   honor the remaining run capacity, shared weekly publisher cap and existing
   event functions.
5. Return strict winners first, followed by fallback winners. Never force the
   requested total. Mark each winner `selection_tier=strict` or `fallback`.

The requested three passes are implemented with a strict reservation: strict
coverage wins first, fallback can address shortages only in capacity left after
protecting strict overflow, and quality overflow finishes allocation. Reserving
strict overflow before fallback is necessary to satisfy the absolute strict
priority rule: a fallback coverage story cannot consume a slot, publisher
allowance or event representative that belongs to a strict winner. With fallback
disabled, the original strict winner set and ordering are preserved.

There is no new scoring formula. Both tiers use the existing 70% final relevance,
20% final significance and 10% publisher quality score and its existing tie-breaks.
Classifier score is retained for the audit; it does not replace final scores.
There is no new LLM call, factual-audit stage, configuration setting or Notion field.

## Files changed in this step

| File | Focused change |
|---|---|
| `src/research_automation/models/candidate.py` | Separate fallback eligibility, selected tier, fallback reason and explicit publication-failure field; strict eligibility is unchanged |
| `src/research_automation/pipeline/luna_selection.py` | Resolve final geography and calculate the existing queue score for possible enriched fallback candidates while preserving their strict rejection |
| `src/research_automation/pipeline/selection.py` | Reuse the coverage/overflow allocator for strict then fallback with protected strict winners and shared constraints; event implementation unchanged |
| `src/research_automation/pipeline/ingestion.py` | Enable two-tier selection only after the existing Luna enrichment loop; print separate counts/tier/reasons and label strict relevance rejections clearly |
| `src/research_automation/pipeline/candidate_audit.py` | Persist tier, fallback qualification/reason, original strict rejection and final decision; expose scores and selection counts in JSON/Markdown |
| `tests/test_two_tier_selection.py` | Focused mocked selection and ingestion regressions |
| `tests/test_luna_selection.py` | Use significance 2 in the test that verifies a high classifier score cannot rescue a failing final assessment |
| `tests/test_luna_shadow_corrections.py` | Keep strict gate/budget assertions; distinguish new fallback winners from strict winners |
| `tests/test_luna_quality_backfill.py` | Preserve prompt/parser/strict-gate checks while expecting eligible fallback selections |
| `docs/luna_selection.md` | Current policy and link to this report; earlier step descriptions retained as history |
| `.preview/luna_two_tier/report.md` | This implementation and verification report |

Verification artifacts: `protected_before.json` records hashes of protected files
and local state plus the original event-helper source. `verification.json` records
the comparison. Neither contains credentials or article bodies.

## Verification

Baseline: **428 passed**. Final full suite: **473 passed**, including **45 new
regression cases** in `test_two_tier_selection.py`. `git diff --check` passed.

Coverage includes all 13 requested regression requirements, relevance 1/2 and
significance-2 exclusions, unregistered relevance 3/4 versus 5, invalid/unclear
regions, explicit publication failures, existing-event and processed-URL
suppression, strongest duplicate representative, cross-tier capacity/publisher/
event priority, distinct-capacity projects, unchanged 48-attempt behavior,
one enrichment per article, persisted audit fields and safe dry-run behavior.

The end-to-end mocked dry run enriched 11 inputs exactly once each: four strict,
five fallback, one relevance-2 rejection and one significance-2 rejection. It
returned **9**, made **zero Notion writes**, and left the existing processed-state
file unchanged. The saved audit was checked against the report, including all
required per-fallback fields and strict/final decision separation.

Protected-file checks cover the classifier, LLM client, both prompts, configuration,
collection, discovery, scoring implementation, Notion schema, `.env`, local state
and all existing event helpers. They must match the pre-edit snapshot.

## Example behavior

| Available candidates | Result with limit 12 |
|---|---|
| 12 strict plus 5 eligible fallback | 12 strict, 0 fallback |
| 4 strict plus 5 eligible fallback | 4 strict, 5 fallback, total 9 |
| 4 strict plus 4 eligible fallback | Total 8 |
| Registered, final relevance 3/significance 4 | Fallback eligible when spare capacity remains |
| Registered, final relevance 3/significance 2 | Rejected |
| Registered, final relevance 2/significance 5 | Rejected |
| Unregistered, relevance 3 or 4 | Rejected; still requires 5 |
| Strict coverage or overflow competes with higher-scoring fallback | Strict wins |
| Fallback in a missing region competes with stronger fallback overflow | Coverage gets first claim on the fallback slot |

Console example:

```text
Strict selections: 4
Fallback selections: 5
Total selections: 9
Notion writes: 0 (dry-run)
```

## Next Luna dry run

From the repository root in PowerShell, with existing `.env` credentials:

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
.\.venv\Scripts\python.exe -u -X utf8 -m scripts.run_daily_ingestion_local --dry-run --all-sources --limit 12
```

This command was not executed in this step. It forces all publishers due and
uses the existing processed/event exclusions. It performs live read/model
requests and writes local diagnostic audits, but does not write to Notion or
update persistent ingestion state. The run limit is a selection ceiling and the
48-attempt enrichment ceiling is not a classifier token or dollar budget.

## Limits

Offline tests establish selection policy, not the editorial accuracy of a fresh
Luna run. Relevance-3 articles can remain borderline despite significance 3; the
unchanged model outputs decide their scores and human review remains necessary.

Ingestion currently has no structured factual-verification verdict. The new
`publication_failure_reason` lets an explicit known failure veto fallback, and
existing non-threshold rejection reasons cannot be overridden. A blocked or failed
fetch alone does not establish falsity, and free-text summaries are not parsed
into factual verdicts. This step adds no factual verification or model request.

Existing bounded event matching can still miss differently worded duplicate
events or overmerge similar headlines. Its implementation is unchanged. Regional
shortages can remain, and either tier may exhaust suitable candidates before
reaching the requested maximum. Deterministic rollback mode keeps its original
strict-only behavior.

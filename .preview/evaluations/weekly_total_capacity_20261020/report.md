# Weekly total capacity enforcement

Implemented only the weekly-volume bound. No live API calls, article collection,
Notion writes or changes to persistent workspace ingestion state occurred during
this task. All ingestion/model/Notion regression runs use offline fixtures.

## Exact algorithm

The existing four regional target values define the weekly total; there is no
additional setting:

```text
weekly_total_target = sum(configured Global/UAE/KSA/Egypt targets)
existing_weekly_total = sum(actual Global/UAE/KSA/Egypt weekly counts)
remaining_weekly_capacity = max(0, weekly_total_target - existing_weekly_total)
effective_run_capacity = min(requested --limit,
                             existing MAX_ARTICLES_PER_RUN bound,
                             remaining_weekly_capacity)
```

Actual counts include every existing regional overflow entry. Positive regional
shortages are not summed to calculate capacity. With targets 3/4/3/2 and the
user-provided existing counts 6/1/1/1, the total is 9, remaining capacity is 3,
and `--limit 12` permits at most 3 new articles. The regional shortages still sum
to 6; that does not create six available weekly slots.

The reusable `select_final_candidates` applies the same remaining-capacity bound
before its existing strict/fallback selection. The strict coverage and strict
quality-overflow passes retain priority; eligible fallback can only fill space
left within that shared cap. Publisher caps, URL/event suppression and the
70/20/10 score are unchanged. Luna regions remain coverage preferences, not hard
ceilings. This does not force the requested count or weaken any eligibility rule.

## Ingestion and efficiency

Ingestion reads the current Dataset Meeting and its queue before weekly setup
can create/update Notion pages. It computes effective capacity before collection
and model work. At zero capacity it returns an empty selection with the existing
state and shortages preserved, writes only the normal local diagnostic audit,
and skips weekly setup writes, collection, direct-site supplementation, discovery,
classification, URL resolution, retrieval, enrichment and source-health writes.
This also applies with `--all-sources` and in live mode.

When space remains, the existing assessment path receives effective capacity as
its run limit. The existing unique strict-winner stop condition therefore stops
at three viable winners in the nine-existing example. The configured 32 initial,
48 maximum and 8 backfill allowances are unchanged. Existing fallback assessment
timing remains unchanged; fallback does not prematurely shorten strict assessment.

Each sequential run reloads current queue state. A mocked live-mode sequence
creates 8, then 4, then 0 Article Queue entries, reaching 12 with no writes or
model calls in the final run. Existing processed-URL and event state still apply.
Capacity is based on the existing primary-region counts for the current Dataset
Meeting. This change does not introduce concurrent-run locking or alter how
weekly queue state is loaded.

## Console and audit

For the supplied example, terminal output includes:

```text
Weekly article target: 12
Existing weekly total: 9
Remaining weekly capacity: 3
Requested run limit: 12
Effective run capacity: 3
```

Both JSON and Markdown audits retain these values. JSON stores them in
`weekly_capacity`, using `weekly_total_target`, `existing_weekly_total`,
`remaining_weekly_capacity`, `requested_run_limit` and `effective_run_capacity`.
These are the initial capacity values for the run; selected/created counts and
remaining regional shortages continue to be reported separately. Raw requested
limits are retained even when the existing per-run maximum also reduces capacity.

## Files changed in this task

| File | Change |
|---|---|
| `src/research_automation/pipeline/selection.py` | Shared weekly-capacity calculation and total cap before existing tier selection. No event/scoring/allocation implementation changes. |
| `src/research_automation/pipeline/ingestion.py` | Read-only capacity check before setup writes; zero-capacity early exit; effective stopping limit; capacity reporting. Shared local-audit finishing routine handles active and skipped runs. |
| `src/research_automation/pipeline/candidate_audit.py` | Capacity snapshot in JSON and the five values in Markdown. |
| `tests/test_weekly_total_capacity.py` | 26 new offline regression cases. |
| `tests/test_luna_shadow_corrections.py` | Two existing test functions now explicitly configure twelve weekly slots for their twelve-winner/budget scenarios. Existing assertions are preserved. |
| `tests/test_two_tier_selection.py` | Two existing test functions now explicitly configure twelve weekly slots for their nine/twelve-selection scenarios. Existing assertions are preserved. |
| `docs/luna_selection.md` | Current capacity, early-exit and reporting behavior. |

The four older test functions previously used a shared fixture configured for
only four weekly articles while expecting nine or twelve selections. Explicit
3/4/3/2 targets keep those tests focused on their original budget/fallback
contracts without relying on the overflow-capacity bug. No production quota
configuration or existing test assertion was changed.

The exact production change relative to this task's starting worktree is in
[implementation.diff](implementation.diff). All prior uncommitted work remains.

## Regression coverage and verification

The 26 new cases cover:

- Empty week, 9 existing with limits 12 and 2, full week, overfull week, and the
  ten-remaining/limit-five example.
- A custom twenty-article target, confirming capacity is derived rather than
  hardcoded to twelve.
- Existing Global overflow consuming capacity even with six positive deficits.
- Strong UAE, Egypt and Global candidates surviving within three remaining
  slots while a weak KSA candidate stays unselected.
- Global quality overflow while regional shortages remain.
- A shared cap across strict/fallback winners, preserving strict priority.
- Sequential selector state and actual mocked live-ingestion sequences 8/4/0.
- Effective-capacity enrichment stopping, unchanged 32/48/8 settings and all five
  console/JSON/Markdown audit values.
- Zero capacity with twelve/fourteen existing articles, both selection modes,
  dry/live operation and `--all-sources`: no setup/Notion/state writes, collection,
  discovery, retrieval or paid model work.
- Read-only dry runs and preserved URL identity on repeated runs.

Baseline full pytest before editing: **797 passed**.
Final full pytest: **823 passed in 8.12 seconds**, including 26 new cases.
`git diff --check`: **exit 0**; Git emits only LF/CRLF advisories for files in
the existing checkout, with no whitespace errors.

Integrity checks covered 137 existing files: the six intended existing files
above changed, with the other 131 unchanged, plus the one new test file.
Classifier/enrichment prompts and clients, resolver, ArticleRetriever, source
acquisition/direct discovery, scoring, editorial scope, region allocation,
same-event implementation, configuration, latest saved shadow audit and
persistent state are preserved. See [verification.json](verification.json).

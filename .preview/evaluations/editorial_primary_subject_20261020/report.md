# Primary-subject editorial correction

Implemented only the detailed-enrichment editorial-scope correction. No live
model, publisher or Notion API calls were made; no articles were collected and
no Notion or persistent ingestion-state writes occurred. Official OpenAI
documentation was consulted for prompt clarity; no model/SDK/API settings changed.

## Files changed

| File | Change |
|---|---|
| `src/research_automation/prompts/article_enrichment.txt` | Primary-subject/system-level conflict test; supported clean-transition requirement; central mission-component test for broad investments. Existing instructions compacted without changing the output contract or scoring scales. |
| `tests/test_editorial_primary_subject.py` | 27 offline tests using synthetic evidence and fixed Luna/Sol judgments through the real prompt renderer, JSON parser and existing final gates. |

The classifier prompt is unchanged. Its existing primary-news distinction and
Borderline handling already support high recall; the detailed evidence-aware
call remains authoritative. There are no production Python, configuration,
acquisition, retrieval, scoring, allocation, publisher-cap or event-dedup edits.

The exact prompt diff is saved as [prompt.diff](prompt.diff), with the original
prompt in [article_enrichment_before.txt](article_enrichment_before.txt).

## Exact central rules

Conflict exception:

> Conflict/geopolitics as context requires a supported causal MATERIAL SYSTEM-LEVEL consequence as PRIMARY news: measurable fertilizer/harvest loss, major irrigation shutdown, blockade halting commercial food imports, substantial national/regional production-capacity loss from war, water-access/infrastructure failure or relevant transition-system disruption. Only then use supply_disruption or the actual mission type.

Primary-subject test:

> Primary-subject test: if removing the mission consequence leaves primarily conflict/politics, keep story_type conflict_security or politics_diplomacy; it is ineligible. Farmer attacks, land seizures or territorial/military/diplomatic events with secondary farm damage stay excluded. Farmer/hectare/local-loss counts alone do not establish system impact; keywords never change the primary type.

Technology/transport:

> Technology/transport relevance >=4 needs supported material electric drivetrain/electrification, emissions cuts, higher-carbon transport replacement, clean public transit, modal shift, energy efficiency or transport decarbonisation. Autonomous/AI/smart-city/futuristic labels alone -> relevance <=3. Explicit electrification needs no quantified emissions; pilot scale/unproven performance affects significance separately.

Broad investments:

> Large investment totals alone are not mission fit. Incidental sustainability in property/construction/economic portfolios -> relevance <=3. Central water, renewable-energy, sustainable-transport, waste/circularity or other mission-linked developments can qualify; only their investment counts.

The remaining guidance preserves direct/indirect mission chains, concrete food
supply shocks and inflation, agricultural funding, water infrastructure,
transition-material policy, substantive climate/environmental measurements,
important mission research and commercial carbon removal. Missing quantified
emissions or project outcomes still affects significance separately from a
clearly established mission connection. No headline-specific rules were added.

## Why the observed cases behave differently

The latest existing audit was read without changing it:
`.preview/ingestion_audits/20261019T192431118208Z_3c66ab89.json`.

Its Golan story was labelled `supply_disruption`; its significance rationale cited
affected hectares/farmers without quantified output loss. The new rule explicitly
prevents such counts or farm damage alone from changing a primarily territorial
or military story into a mission-development type. A genuinely primary regional
production collapse or major irrigation shutdown still qualifies for assessment.

Autonomy, AI and futuristic transport labels no longer justify a high relevance
score without supported transition evidence. A real electric deployment may still
qualify. The existing pod-story audit rationale mentions electric transit; that
statement is not independent verification of the publisher body, and this task
does not claim that the actual article must be rejected under the new rubric.

Likewise, the broad construction-portfolio rationale mentions water/grid/sewerage
investments. The model must determine whether those are the central substantive
development in the supplied evidence. A headline's large total alone is
insufficient; a central major mission-infrastructure component remains eligible.

## Offline scenarios and expected contract

All bodies/titles in the new tests are explicitly synthetic. They are not
reconstructed publisher evidence or missing historical snippets.

| Scenario | Fixed detailed judgment | Existing final gate |
|---|---|---|
| Territorial expansion with individual farmer/land damage | `conflict_security`, deliberately high 4/4 scores | Both tiers reject primary type. |
| Diplomatic dispute with incidental farm access damage | `politics_diplomacy`, deliberately high 5/4 scores | Both tiers reject primary type. |
| Conflict-induced substantial regional staple-capacity loss | `supply_disruption`, relevance/significance 4/4 | Strict eligible. |
| Autonomous pilot with no supported transition link | Relevance/significance 3/2 | Strict rejects; fallback significance floor also fails. |
| Electric public transit explicitly replacing diesel, no quantified achieved emissions | `infrastructure_project`, 4/3 | Strict eligible. |
| Broad construction portfolio with incidental sustainability | Relevance/significance 3/2 | Strict rejects; fallback significance floor also fails. |
| Major water-reuse/desalination/renewable portfolio | `investment_financing`, 4/4 | Strict eligible. |
| Hormuz fertilizer shortage materially lowering harvest forecasts | `supply_disruption`, 4/4 | Strict eligible. |
| Concrete global grain-supply shocks causing food inflation | `supply_disruption`, 4/4 | Strict eligible. |
| Transition-mineral financing policy | `policy_regulation`, 4/4 | Strict eligible. |
| Important new systemic climate measurement | `research_result`, 4/4 | Strict eligible. |
| Commercial carbon-removal agreement | `investment_financing`, 4/3 | Strict eligible. |

These twelve scenarios run with each existing enrichment model (24 cases), plus
two tests preserving the 3/3 fallback boundary and one rubric-preservation test.
The tests check actual rendered instructions, supplied article evidence, one
existing enrichment call, parsing, primary-type exclusion, strict qualification,
fallback behavior, unchanged queue scoring, audit provenance and dry-run safety.
They do not evaluate real-model prediction accuracy.

## Fallback boundary retained

Relevance <=3 is a strict-tier cap, not a new blanket queue exclusion. Under the
unchanged fallback rules a registered article with relevance 3 and significance
>=3 can still qualify if the other requirements pass. The two explicit boundary
tests demonstrate this for transport and portfolio judgments. Primary
`conflict_security`/`politics_diplomacy` remains excluded from both tiers regardless
of relevance or significance. No fallback threshold was changed implicitly.

## Prompt size and verification

The first wording expansion exceeded the existing historical offline experiment's
hard request reservation. Rather than change its budget, the final prompt
compacts repeated instructions while retaining the earlier evidence, novelty,
mission and score-separation guidance. Its text is 8,355 characters versus 8,353
before. The historical 29-request offline preflight reserves 699,107 of its
unchanged 700,000 conservative units (699,059 before). These are offline planning
reservations, not actual token usage or a billed model run.

- Baseline full suite before edits: **770 passed**.
- Final full suite: **797 passed in 7.29 seconds**, including 27 new cases.
- `git diff --check`: exit 0. The pre-existing checkout emits an LF/CRLF advisory
  for `luna_selection.py`, which was not edited in this task.
- Protected baseline: 135 existing files checked; only the intended enrichment
  prompt changed, with the other 134 unchanged. The latest shadow audit, actual
  environment, persistent state, classifier prompt, resolver/retriever and
  production selection/configuration were preserved.
- No live model calls, article collection, Notion writes or state changes.

Detailed integrity/preflight values are in [integrity.json](integrity.json).
The existing 1-5 scales, strict/fallback thresholds, 70/20/10 weights, 32/48/8
enrichment allowances, batch size 100, geography, caps and same-event behavior
remain unchanged. A later authorized live evaluation would be needed to measure
whether the prompt changes improve real Luna/Sol editorial judgments.

Prompting source consulted: [OpenAI Docs: prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering).

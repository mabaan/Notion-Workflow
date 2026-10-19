# First Luna shadow run: downstream correction report

Source: [20261018T221758362749Z_58f6bc9e.json](../ingestion_audits/20261018T221758362749Z_58f6bc9e.json); SHA-256 `e445401e2d3f2e58240f8d61ac2c695a7cd6aed7a779575d84115eefc6990196`.

The exact Markdown and JSON audit were inspected before source edits. This pass used mocked/offline tests only. The original audit is unchanged. Full ranked records and classification reasons are in [analysis.json](analysis.json).

## Audit findings

The 1,469 input records reconcile to 649 objective exclusions and 820 classifications. Classification has nine requests, no unresolved IDs and 674 Irrelevant decisions. The remaining 146 candidates reconcile to 32 enrichments, 76 budget deferrals and 38 pre-enrichment cap rejections.

Of the 76 budget-exhausted candidates, seven were Relevant/4, 27 Borderline/3 and 42 Borderline/2. None was Relevant/5. The 38 cap rejections were 25 Reuters and 13 Saudi Press Agency: eight Relevant/4, 15 Borderline/3 and 15 Borderline/2.

Highest reviewed budget deferrals include the Arab News Hormuz-reopening proposal, Guardian West Bank harvest-interference report, Guardian Amazon record-low deforestation report, and Guardian EV-battery/nickel deforestation investigation. The highest cap-rejected candidate is Reuters on record-low Amazon deforestation; the seven other Relevant/4 cap rejections concern routine SPA water/food/meal assistance. The tables below list every deferred/capped record.

Review order uses classifier decision, classifier score, source quality and freshness, with ID as a display tie-break. It does not reconstruct the full region/diversity allocation or pretend that phase-local metadata ranks are globally comparable. Original URLs and snippets were not retained in the audit.

### Were stronger stories demonstrably missed?

There are plausible editorial improvements to review, especially the Reuters Amazon story and Guardian battery-supply-chain investigation. Their final relevance/significance are absent: neither can be proven to outrank a winner from this audit. No hidden fresh ACWA/Iraq solar, Saudi BESS or major water-infrastructure project was found among these unassessed groups. Budget expansion does not guarantee twelve strong winners.

The ACWA/Iraq solar headline is absent. The three other ACWA water headlines and the Iraq $1.32bn desalination pipeline were excluded for freshness. The concrete named storage projects from earlier benchmarks are absent; fresh storage-related items are mostly basic science plus the Guardian supply-chain investigation. The National Veal Project qualified at relevance 4/significance 3. Saudi Reef/Jazan SAR1.2bn support reached enrichment but scored 3/3 with insufficient content; the audit rationale explicitly notes missing allocation, timing and measurable-results detail. This is a review concern, not proof that the final relevance must be raised. The two UAE national food-strategy reports both qualified at 5/4. See all known-case fates below.

### The recorded same-event rejection

Arab News and Reuters both carried "UN says Gaza malnutrition gains fragile as commercial supplies halt". Reuters survived with source quality 9 versus 8, equal relevance 4 and significance 3, queue score 77 versus 76. The title-based suppression worked for this pair.

The UAE strategy pair did not match under the old comparison. Replaying the nine qualified records with recorded scores and dates, empty weekly state and canonical hashes as identities reproduces eight old winners; the new comparison leaves seven and keeps AGBI (96) over Fast Company Middle East (91). No missing snippets or fresh model scores were invented. This replay isolates deduplication and does not predict the revised prompt or adaptive allocator.

## Exact corrections

- `pipeline/luna_selection.py`: remove the publisher-cap pre-rejection; use soft publisher round-robin, with classifier decision/score/quality/freshness ranking each publisher's turn, carrying prior attempts and existing weekly counts between allocation batches. Four candidates from one publisher remain assessable. Existing queue events remain suppressed before enrichment; provisional in-run winners no longer become a pre-enrichment hard gate.
- `pipeline/ingestion.py`: retain RSS classification and optional discovery classification; preserve the 24/8 RSS/fallback split inside the initial 32. After initial attempts, assess pending Relevant/Borderline candidates in batches of eight, to at most 48. Recompute constrained final selection after each attempt and stop as soon as the requested number of unique viable winners exists. Failed attempts count; no article is enriched twice.
- `config.py` / `.env.example`: new INITIAL_BUDGET=32, MAX_BUDGET=48 and BACKFILL_BATCH=8. MAX_BUDGET above 48 is rejected. Legacy ARTICLE_ENRICHMENT_BUDGET remains an initial-budget alias; the new initial setting takes precedence. For the old fixed-cost behavior, set INITIAL_BUDGET and MAX_BUDGET equal.
- `prompts/article_enrichment.txt`: relevance 4 normally requires substantive financing, capacity, infrastructure, policy, commercial deployment, supply-chain or resource-security consequences. Festivals, seasonal reports, tourism, ordinary labels, local sales and relief deliveries generally remain <=3 without supported broader consequences. Core financing, structural malnutrition/supply, capacity and food-strategy cases stay eligible. Significance stays separate; thresholds and 70/20/10 are unchanged.
- `pipeline/selection.py`: retain exact canonical URL matching and the existing title comparison. Guard conflicting event countries and like-unit capacity/percentage measures. Add a narrow policy-announcement match requiring shared action/policy anchors, event country, publication proximity <=3 days and strong normalized-title containment or snippet overlap. Strongest final representative wins; unrelated ACWA projects and the related Hormuz pair stay distinct. Existing queued-event title behavior remains.
- `pipeline/candidate_audit.py`: record initial/max/batch/actual attempts and consistent explicit deferrals.
- Tests: `test_luna_shadow_corrections.py`, `fixtures/luna_shadow_qualified.json`, `test_config.py`; existing fixed-budget cases in `test_luna_selection.py` now explicitly set the maximum. `docs/luna_selection.md` links and describes this correction.

## Tests and limits

Full offline suite: **410 passed** (372 before this pass); `git diff --check` passed. Thirty-three new integration/editorial/event cases and five configuration cases cover the requested behavior. The prompt tests deliver fixed outputs through the real renderer/parser and unchanged threshold; they do not prove future model judgments. No model or provider request limits, coverage targets, human approval, schema or deterministic rollback were changed.

Mock budget outcomes: 32 sufficient -> 32 attempts; eight winners at 32 -> 40 attempts to reach twelve; enough at 35 -> stop at 35; still eight after 48 -> stop at 48; a configured maximum of 43 clamps the last batch. Unique-event and final publisher constraints drive the stop count.

Remaining limits: sparse metadata and model variability persist; broader same-event paraphrases can remain undetected, especially missing dates/geography and existing queue records that expose only titles. Diversity is soft, not an additional publisher hard cap; a publisher may predominate where alternatives are unavailable for requested regional coverage. The 48-attempt limit is not a token/dollar cap and existing client retries still apply. Real editorial benefit and cost require the next user-launched dry run.

## Next Luna dry run

No paid dry run was launched. These PowerShell commands are for the user to run from the repository root. They use read-only Notion queries and local metadata audits; `--limit` controls winners, not model spend.

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

The default selection mode remains deterministic. Original audit and persistent-state integrity checks are recorded in [integrity.json](integrity.json).

## All enrichment budget exhausted candidates

| Review rank | Title / publisher | Classifier | Region / quality | Recorded metadata / allocation rank | Outcome |
|---:|---|---|---|---|---|
| 1 | Iran urges US to accept proposal to reopen Strait of Hormuz - Arab News / Arab News | Relevant 4/5 | Global / 8.0 | 4 / 9 | enrichment budget exhausted |
| 2 | Israeli settlers attack European diplomats in West Bank / The Guardian International | Relevant 4/5 | Global / 8.0 | 5 / 25 | enrichment budget exhausted |
| 3 | Brazilian Amazon deforestation falls to lowest on record as pivotal vote looms / The Guardian International | Relevant 4/5 | Global / 8.0 | 6 / None | enrichment budget exhausted |
| 4 | Revealed: VW, Ford and Tesla batteries linked to destructive deforestation of indigenous lands / The Guardian International | Relevant 4/5 | Global / 8.0 | 7 / None | enrichment budget exhausted |
| 5 | Saudi-led coalition and Houthis trade threats over oil installations - The National / The National | Relevant 4/5 | Global / 6.0 | 8 / None | enrichment budget exhausted |
| 6 | The Hormuz Inflection: Energy Security and Connectivity Networks in the Middle East / orfonline.org | Relevant 4/5 | Global / None | 10 / None | enrichment budget exhausted |
| 7 | Can processed food exports ease Egypt’s currency crisis? - EUROPE SAYS / europesays.com | Relevant 4/5 | Egypt / None | 11 / None | enrichment budget exhausted |
| 8 | Water treatment research opportunities at synchrotron and neutron user facilities - Nature / Nature | Borderline 3/5 | Global / 10.0 | 12 / None | enrichment budget exhausted |
| 9 | Hydroxy artificial water channels enable ultraselective reverse osmosis membranes for N -nitrosamine removal in water reuse - Nature / Nature | Borderline 3/5 | Global / 10.0 | 13 / None | enrichment budget exhausted |
| 10 | US plans to ease sanctions on shadow fleet - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 3/5 | Global / 10.0 | 14 / None | enrichment budget exhausted |
| 11 | Two vessels sink off Oman as Hormuz attacks intensify - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 3/5 | Global / 10.0 | 15 / None | enrichment budget exhausted |
| 12 | Trump’s Russian diesel fix comes at a price - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 3/5 | Global / 10.0 | 16 / None | enrichment budget exhausted |
| 13 | Israeli forces fire tear gas at olive farmers near Ramallah - Arab News / Arab News | Borderline 3/5 | Global / 8.0 | 17 / None | enrichment budget exhausted |
| 14 | Iran president says conflict in Middle East amounts to ‘ecocide’ - Arab News / Arab News | Borderline 3/5 | Global / 8.0 | 18 / None | enrichment budget exhausted |
| 15 | EU, Yemen government urge Houthis to lift siege of Taiz - Arab News / Arab News | Borderline 3/5 | Global / 8.0 | 19 / None | enrichment budget exhausted |
| 16 | Experts call for adaptive economic policies to boost agritech, manufacturing and supply-chain resilience as SIF 2026 concludes - Zawya / ZAWYA | Borderline 3/5 | Out of Scope/Unclear / 6.0 | 21 / None | enrichment budget exhausted |
| 17 | Attacks on Gulf energy infrastructure 'worrying' for Islamabad, Pak Finance Minister says - Khaleej Times / Khaleej Times | Borderline 3/5 | Global / 6.0 | 22 / None | enrichment budget exhausted |
| 18 | Dubai RTA awards $100,000 prize to Jordan's bus project, Dh240,000 to UAE students - Gulf News / Gulf News | Borderline 3/5 | Global / 6.0 | 23 / None | enrichment budget exhausted |
| 19 | Iraq's economic slowdown to affect government spending, strategic projects exempt: Adviser - Zawya / ZAWYA | Borderline 3/5 | Global / 6.0 | 24 / None | enrichment budget exhausted |
| 20 | IEA oil supply pledge to exceed target as it boosts release of remaining stocks - The National / The National | Borderline 3/5 | Global / 6.0 | 25 / None | enrichment budget exhausted |
| 21 | Oil transfers off India's west coast surge as Gulf shipping congestion worsens - The National / The National | Borderline 3/5 | Global / 6.0 | 26 / None | enrichment budget exhausted |
| 22 | US-Israel-Iran war: Ships sunk, flights cancelled, trade rerouted — your Oct. 15 briefing - Gulf News / Gulf News | Borderline 3/5 | Global / 6.0 | 27 / None | enrichment budget exhausted |
| 23 | African Energy Bank to begin deployment of financing to energy projects in 2027 - Zawya / ZAWYA | Borderline 3/5 | Out of Scope/Unclear / 6.0 | 28 / None | enrichment budget exhausted |
| 24 | Under siege: Taiz isolated and afraid as Houthis and Yemeni forces fight over city - The National / The National | Borderline 3/5 | Global / 6.0 | 29 / None | enrichment budget exhausted |
| 25 | 'He irrigated the tree with his blood': West Bank olive farmers set for another deadly harvest - The National / The National | Borderline 3/5 | Global / 6.0 | 30 / None | enrichment budget exhausted |
| 26 | US military counters Iran's claim, says helped ship 19 million barrels of oil through Hormuz on Monday - Gulf News / Gulf News | Borderline 3/5 | Global / 6.0 | 31 / None | enrichment budget exhausted |
| 27 | IMF cuts 2026 growth forecasts for Gulf economies due to prolonged Hormuz closure - The National / The National | Borderline 3/5 | Global / 6.0 | 32 / None | enrichment budget exhausted |
| 28 | Shipping alert: Strait of Hormuz crisis deepens as 3 vessels struck by unknown projectiles - Gulf News / Gulf News | Borderline 3/5 | Global / 6.0 | 33 / None | enrichment budget exhausted |
| 29 | Hormuz attack: India's seafarers union seeks 'urgent update' on missing sailors - Khaleej Times / Khaleej Times | Borderline 3/5 | Global / 6.0 | 34 / None | enrichment budget exhausted |
| 30 | Egypt’s Gulf Anchor: From Financial Lifeline to Energy Buffer - ORF Middle East / orfme.org | Borderline 3/5 | Egypt / None | 37 / None | enrichment budget exhausted |
| 31 | Saudi Says Energy Export Capability Intact \| Rigzone / rigzone.com | Borderline 3/5 | KSA / None | 38 / None | enrichment budget exhausted |
| 32 | Saudis’ Ability to Supply Energy Is Resilient, Minister Says - Bloomberg / bloomberg.com | Borderline 3/5 | KSA / None | 39 / None | enrichment budget exhausted |
| 33 | Saudi Minister stresses global energy security, resilience at opening of 25th WPC Congress / tradearabia.com | Borderline 3/5 | KSA / None | 40 / None | enrichment budget exhausted |
| 34 | Saudi Arabia Hosts Energy Summit as It Trades Strikes With Houthis - The New York Times / nytimes.com | Borderline 3/5 | KSA / None | 41 / None | enrichment budget exhausted |
| 35 | Iraq puts losses from US-Iran war at $60bn - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | Global / 10.0 | 42 / None | enrichment budget exhausted |
| 36 | Cargo operators find Riyadh workarounds – at a price - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | KSA / 10.0 | 43 / None | enrichment budget exhausted |
| 37 | Iran threatens tanker-shuttle system in Gulf of Oman attacks - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | Global / 10.0 | 44 / None | enrichment budget exhausted |
| 38 | War will hinder growth until 2030, IMF warns - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | Global / 10.0 | 45 / None | enrichment budget exhausted |
| 39 | QatarEnergy reveals steep fall in profit and revenue - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | Global / 10.0 | 46 / None | enrichment budget exhausted |
| 40 | Qatar companies get grant to offset higher shipping costs - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | Global / 10.0 | 47 / None | enrichment budget exhausted |
| 41 | electrolysis interfaces at application-relevant current density reveals water gating - Nature / Nature | Borderline 2/5 | Global / 10.0 | 48 / None | enrichment budget exhausted |
| 42 | Global conservation area coverage substantially exceeds current estimates - Nature / Nature | Borderline 2/5 | Global / 10.0 | 49 / None | enrichment budget exhausted |
| 43 | Evidence for multi-Li+ clustering in lithium-ion battery electrolytes - Nature / Nature | Borderline 2/5 | Global / 10.0 | 50 / None | enrichment budget exhausted |
| 44 | Protecting nature means valuing biodiversity - Nature / Nature | Borderline 2/5 | Out of Scope/Unclear / 10.0 | 51 / None | enrichment budget exhausted |
| 45 | Saudi Arabia expands pipelines to reduce reliance on Hormuz - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | KSA / 10.0 | 52 / None | enrichment budget exhausted |
| 46 | IMF forecasts Middle East GDP contraction as war drags on - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | Global / 10.0 | 53 / None | enrichment budget exhausted |
| 47 | Flight disruptions spread following Riyadh airport attack - Arabian Gulf Business Insight \| AGBI / AGBI | Borderline 2/5 | KSA / 10.0 | 54 / None | enrichment budget exhausted |
| 48 | US Gulf Coast gas infrastructure may struggle to keep pace with LNG, power growth - S&P Global / S&P Global | Borderline 2/5 | Out of Scope/Unclear / 9.0 | 55 / None | enrichment budget exhausted |
| 49 | Saudi Arabia seizes 1.3 million noncompliant products, conducts over 144,000 inspections in Q3 - Saudi Gazette / Saudi Gazette | Borderline 2/5 | KSA / 8.0 | 56 / None | enrichment budget exhausted |
| 50 | Syrian finance minister discusses development with Qatar, Norway - Arab News / Arab News | Borderline 2/5 | Global / 8.0 | 57 / None | enrichment budget exhausted |
| 51 | Israeli settlers attack European diplomats in West Bank amid surge in olive harvest violence - Arab News / Arab News | Borderline 2/5 | Global / 8.0 | 58 / None | enrichment budget exhausted |
| 52 | Saudi Civil Defense warns of flash floods as thunderstorms sweep across Kingdom - Arab News / Arab News | Borderline 2/5 | KSA / 8.0 | 59 / None | enrichment budget exhausted |
| 53 | No 10 leaves option open to impose Chinese EV tariffs if UK joins EU scheme / The Guardian International | Borderline 2/5 | Out of Scope/Unclear / 8.0 | 60 / None | enrichment budget exhausted |
| 54 | Iran ships some LPG, jet fuel despite US blockade, data shows - Arab News / Arab News | Borderline 2/5 | Global / 8.0 | 61 / None | enrichment budget exhausted |
| 55 | US military weighs use of ‘mother of all bombs’ in potential future strikes on Iran, CNN says - Arab News / Arab News | Borderline 2/5 | Global / 8.0 | 62 / None | enrichment budget exhausted |
| 56 | Red alerts issued as heavy thunderstorms, flash floods threaten several Saudi regions - Saudi Gazette / Saudi Gazette | Borderline 2/5 | KSA / 8.0 | 63 / None | enrichment budget exhausted |
| 57 | Coalition orders evacuation of Sanaa oil facility ahead of military operation - Saudi Gazette / Saudi Gazette | Borderline 2/5 | Global / 8.0 | 64 / None | enrichment budget exhausted |
| 58 | Cyberattack on French supermarkets causes fires, millions in losses - Saudi Gazette / Saudi Gazette | Borderline 2/5 | Out of Scope/Unclear / 8.0 | 65 / None | enrichment budget exhausted |
| 59 | Gulf International Bank reports significant improvement in its sustainability performance - Zawya / ZAWYA | Borderline 2/5 | Global / 6.0 | 66 / None | enrichment budget exhausted |
| 60 | Settlers beat Washington Post journalist during attack on Palestinian olive harvest - The National / The National | Borderline 2/5 | Global / 6.0 | 67 / None | enrichment budget exhausted |
| 61 | World Bank sets fivefold minerals goal as Fed chairman Warsh flags financial stability risks - The National / The National | Borderline 2/5 | Global / 6.0 | 69 / None | enrichment budget exhausted |
| 62 | Bahrain: Muharraq Development Project Phase I work enters fast-track - Zawya / ZAWYA | Borderline 2/5 | Global / 6.0 | 70 / None | enrichment budget exhausted |
| 63 | US military disputes Iran’s Hormuz claims, ship-sinking account - Gulf News / Gulf News | Borderline 2/5 | Global / 6.0 | 71 / None | enrichment budget exhausted |
| 64 | Three dead in Istanbul as torrential rain floods Turkish city - The National / The National | Borderline 2/5 | Global / 6.0 | 72 / None | enrichment budget exhausted |
| 65 | Emaar to invest $17 billion in Syria; Alabbar says opportunity too strong to ignore - Khaleej Times / Khaleej Times | Borderline 2/5 | Global / 6.0 | 73 / None | enrichment budget exhausted |
| 66 | Fire, sinking and reported scramble for cargo: what we know about ship lost in Strait of Hormuz - The National / The National | Borderline 2/5 | Global / 6.0 | 74 / None | enrichment budget exhausted |
| 67 | IMF official says Iran war price shock buffers are narrowing - The National / The National | Borderline 2/5 | Global / 6.0 | 75 / None | enrichment budget exhausted |
| 68 | Fire that broke out on floating platform in Abu Dhabi brought under control - Khaleej Times / Khaleej Times | Borderline 2/5 | UAE / 6.0 | 76 / None | enrichment budget exhausted |
| 69 | Dubai to Riyadh via Bahrain: Travellers take longer routes amid airport disruptions - Khaleej Times / Khaleej Times | Borderline 2/5 | Global / 6.0 | 77 / None | enrichment budget exhausted |
| 70 | Gulf LNG recovery to ease global gas prices from 2027, but supply risks remain: GlobalData - Zawya / ZAWYA | Borderline 2/5 | Global / 6.0 | 78 / None | enrichment budget exhausted |
| 71 | Elsewedy Electric joint venture secures $2.2bln Saudi power project - Zawya / ZAWYA | Borderline 2/5 | KSA / 6.0 | 79 / None | enrichment budget exhausted |
| 72 | What if you could travel beneath Dubai? RTA studies underground transport network for the first time - Gulf News / Gulf News | Borderline 2/5 | UAE / 6.0 | 80 / None | enrichment budget exhausted |
| 73 | World economy near its breaking point, IMF cautions - Gulf News / Gulf News | Borderline 2/5 | Global / 6.0 | 81 / None | enrichment budget exhausted |
| 74 | Saudi Arabia on alert as heavy rain and flash floods threaten regions - Gulf News / Gulf News | Borderline 2/5 | KSA / 6.0 | 82 / None | enrichment budget exhausted |
| 75 | Timeline: Houthis escalate attacks on Saudi airports - The National / The National | Borderline 2/5 | KSA / 6.0 | 83 / None | enrichment budget exhausted |
| 76 | UAE’s Sheikh Abdullah To Meet Jaishankar: Trade, Energy And Regional Security On Agenda \| Outlook India / outlookindia.com | Borderline 2/5 | UAE / None | 84 / None | enrichment budget exhausted |

## All publisher weekly cap candidates

| Review rank | Title / publisher | Classifier | Region / quality | Recorded metadata / allocation rank | Outcome |
|---:|---|---|---|---|---|
| 1 | Deforestation in Brazil's Amazon falls to all-time low - Reuters / Reuters | Relevant 4/5 | Global / 9.0 | 11 / None | publisher weekly cap |
| 2 | KSrelief Distributes 60,000 Liters of Drinking Water in Yemen's Taiz - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 4/5 | Global / 7.0 | 17 / None | publisher weekly cap |
| 3 | KSrelief Distributes 401 Food Baskets to Displaced Families in Yemen’s Abyan - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 4/5 | Global / 7.0 | 18 / None | publisher weekly cap |
| 4 | KSrelief Distributes 836 Food Baskets in Aden, Yemen - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 4/5 | Global / 7.0 | 19 / None | publisher weekly cap |
| 5 | KSrelief Distributes 1,050 Food Baskets to Displaced Families in Yemen - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 4/5 | Global / 7.0 | 20 / None | publisher weekly cap |
| 6 | KSrelief Distributes 654 Food Baskets to Displaced Families in Yemen's Hadhramaut - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 4/5 | Global / 7.0 | 21 / None | publisher weekly cap |
| 7 | KSrelief Distributes 1,269 Food Baskets to Displaced Families in Yemen’s Abyan - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 4/5 | Global / 7.0 | 22 / None | publisher weekly cap |
| 8 | KSrelief Continues Distributing Hot Meals to Most Vulnerable Groups in Gaza Strip - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 4/5 | Global / 7.0 | 23 / None | publisher weekly cap |
| 9 | Iran urges US to accept proposal to reopen Strait of Hormuz - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 35 / None | publisher weekly cap |
| 10 | Iran's Guards say two tankers hit mines in Strait of Hormuz - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 36 / None | publisher weekly cap |
| 11 | Israeli settlers burn olive trees, injure journalist in West Bank attack - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 37 / None | publisher weekly cap |
| 12 | EXCLUSIVE: Iran ships some LPG, jet fuel despite US blockade, data shows - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 38 / None | publisher weekly cap |
| 13 | Israel says commercial goods no longer entering Gaza after merchants suspend coordination - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 39 / None | publisher weekly cap |
| 14 | Canada's farmers, crop quality assessors confront damage after wet harvest - Reuters / Reuters | Borderline 3/5 | Out of Scope/Unclear / 9.0 | 40 / None | publisher weekly cap |
| 15 | Gulf cost edge keeps chemical buyers hooked despite Hormuz risks - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 41 / None | publisher weekly cap |
| 16 | Iran’s precision strikes picked apart Gulf infrastructure, blunting US war plans - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 42 / None | publisher weekly cap |
| 17 | Prolonged war, renewed disruptions pose biggest risk to Middle East region, IMF says - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 43 / None | publisher weekly cap |
| 18 | Iran shifting tactics to step up attacks on shipping before US vote, officials say - Reuters / Reuters | Borderline 3/5 | Global / 9.0 | 45 / None | publisher weekly cap |
| 19 | King Faisal University Study Highlights Potential of Al-Hasawi Lime, Date Molasses in Developing Functional Foods - وكالة الأنباء السعودية / Saudi Press Agency | Borderline 3/5 | KSA / 7.0 | 52 / None | publisher weekly cap |
| 20 | Pomegranate Festival in Al-Baha Attracts Visitors in Its 15th Edition - وكالة الأنباء السعودية / Saudi Press Agency | Borderline 3/5 | KSA / 7.0 | 53 / None | publisher weekly cap |
| 21 | Riyadh Strengthens Role as Global Energy Dialogue Hub, Hosts International Conferences, Ministerial Meetings - وكالة الأنباء السعودية / Saudi Press Agency | Borderline 3/5 | KSA / 7.0 | 54 / None | publisher weekly cap |
| 22 | Ministry of Energy: Saudi Aramco Administrative Building in Dhahran Targeted, No Injuries Reported - وكالة الأنباء السعودية / Saudi Press Agency | Borderline 3/5 | KSA / 7.0 | 55 / None | publisher weekly cap |
| 23 | WPC Energy Congress Examines Economic Transformation and Fiscal Sustainability - وكالة الأنباء السعودية / Saudi Press Agency | Borderline 3/5 | KSA / 7.0 | 56 / None | publisher weekly cap |
| 24 | IMF/World Bank meetings leave developing countries with more questions than answers - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 86 / None | publisher weekly cap |
| 25 | Bank of Canada sees sharply higher inflation outlook as oil surges, Macklem says - Reuters / Reuters | Borderline 2/5 | Out of Scope/Unclear / 9.0 | 87 / None | publisher weekly cap |
| 26 | Tanker struck by unknown projectile off Saudi Arabia on Friday, UKMTO says - Reuters / Reuters | Borderline 2/5 | KSA / 9.0 | 88 / None | publisher weekly cap |
| 27 | COMMENTARY: AI jitters, Trump's fading oil clout and China shock 2.0: The financial week in five charts - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 89 / None | publisher weekly cap |
| 28 | Wall Street tumbles as worries about AI trade and high oil prices weigh - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 90 / None | publisher weekly cap |
| 29 | Global fuel oil market stays tight as conflicts hit Mideast, Russia supplies, Vitol says - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 91 / None | publisher weekly cap |
| 30 | Mideast war alters global bunker buying patterns, industry execs say - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 92 / None | publisher weekly cap |
| 31 | IEA to speed up oil stocks release including over 20 million barrels of diesel - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 93 / None | publisher weekly cap |
| 32 | Yemen's Houthis hit palace in Aden, coalition details attacks on Saudi infrastructure - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 94 / None | publisher weekly cap |
| 33 | How the Houthis are helping Iran turn Saudi Arabia into a pressure point - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 95 / None | publisher weekly cap |
| 34 | US issues fresh Iran-related sanctions, Treasury website shows - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 96 / None | publisher weekly cap |
| 35 | TotalEnergies flags quarterly profit surge as Iran war continues to drive energy prices - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 97 / None | publisher weekly cap |
| 36 | WTO chief sees lasting impact on trade from Middle East war and geopolitics - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 98 / None | publisher weekly cap |
| 37 | Gulf markets mixed; Saudi stocks hardest hit on Aramco attack - Reuters / Reuters | Borderline 2/5 | Global / 9.0 | 100 / None | publisher weekly cap |
| 38 | Tabuk Urban Development Covers 417 Square Kilometers - وكالة الأنباء السعودية / Saudi Press Agency | Borderline 2/5 | KSA / 7.0 | 111 / None | publisher weekly cap |

## Known examples: ACWA / Iraq solar

| Review rank | Title / publisher | Classifier | Region / quality | Recorded metadata / allocation rank | Outcome |
|---:|---|---|---|---|---|
| 1 | Acwa and PT GARAM to build $400 million desalination and salt project in Indonesia - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 2 | Acwa and Veolia expand desalination partnership to cover the full plant lifecycle - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 3 | ACWA Power, GIC to develop $4 billion Az-Zour North 2 & 3 power and water megaproject in Kuwait - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |

## Known examples: Battery / storage

| Review rank | Title / publisher | Classifier | Region / quality | Recorded metadata / allocation rank | Outcome |
|---:|---|---|---|---|---|
| 1 | FEATURE: Low gas storage, LNG disruption to test European resilience in Q2 - S&P Global / S&P Global | None None/5 | None / 9.0 | None / None | outside freshness window |
| 2 | INTERVIEW: Minister outlines Morocco's expanding role in battery, EV supply chains - S&P Global / S&P Global | None None/5 | None / 9.0 | None / None | outside freshness window |
| 3 | A dendrite-sensing composite solid electrolyte for smart lithium batteries - Nature / Nature | Irrelevant 1/5 | Out of Scope/Unclear / 10.0 | None / None | Luna classified irrelevant |
| 4 | Evidence for multi-Li+ clustering in lithium-ion battery electrolytes - Nature / Nature | Borderline 2/5 | Global / 10.0 | 50 / None | enrichment budget exhausted |
| 5 | Your battery may not be a battery - Nature / Nature | Irrelevant 1/5 | Global / 10.0 | None / None | Luna classified irrelevant |
| 6 | Germany gas storage low but no supply risk, regulator says - Reuters / Reuters | Irrelevant 1/5 | Out of Scope/Unclear / 9.0 | None / None | Luna classified irrelevant |
| 7 | EU gas storage passes baseline 75% filling threshold - S&P Global / S&P Global | None None/5 | None / 9.0 | None / None | outside freshness window |
| 8 | Australia names offshore site for Inpex-led Bonaparte carbon storage project - Reuters / Reuters | Irrelevant 1/5 | Out of Scope/Unclear / 9.0 | None / None | Luna classified irrelevant |
| 9 | Battery storage to drive lithium demand growth globally - S&P Global / S&P Global | None None/5 | None / 9.0 | None / None | outside freshness window |
| 10 | Revealed: VW, Ford and Tesla batteries linked to destructive deforestation of indigenous lands / The Guardian International | Relevant 4/5 | Global / 8.0 | 7 / None | enrichment budget exhausted |

## Known examples: Water infrastructure

| Review rank | Title / publisher | Classifier | Region / quality | Recorded metadata / allocation rank | Outcome |
|---:|---|---|---|---|---|
| 1 | Acwa and PT GARAM to build $400 million desalination and salt project in Indonesia - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 2 | Acwa and Veolia expand desalination partnership to cover the full plant lifecycle - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 3 | Water treatment research opportunities at synchrotron and neutron user facilities - Nature / Nature | Borderline 3/5 | Global / 10.0 | 12 / None | enrichment budget exhausted |
| 4 | AQUAHUB advances towards the validation of innovative technologies for wastewater treatment in collaboration with Canal de Isabel II - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 5 | The evolution of rates in desalination (Part I) - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 6 | Ten facts about water desalination - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 7 | Malta opens tender for new Pembroke desalination plant - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 8 | Nesma & Partners and Saur sign MoU for Riyadh water plants - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 9 | Sundt breaks ground on Denton wastewater plant expansion - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 10 | Va Tech Wabag to build new wastewater plant in Delhi - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 11 | Israel to build largest desalination plant in the country - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 12 | Thames Water awards £150m wastewater upgrade work to Costain - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 13 | Angola awards $200 million contract for major desalination plant - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 14 | Qatar signs partnership to recycle wastewater sludge into clean energy - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 15 | San José taps Brown and Caldwell for $240 million wastewater upgrade - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 16 | North Carolina allocates $215 million to rebuild and strengthen water infrastructure - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 17 | PowerChina subsidiary wins $1.32 billion contract for Iraq desalination pipeline - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 18 | Namibia initiates construction of second desalination plant amid severe century-long drought - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 19 | Kuwaiti-Indian consortium offers lowest bid for $377 million desalination project in Kuwait - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 20 | EBRD to invest €35 million in water infrastructure in Ganja, Azerbaijan - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 21 | Kenya approves water infrastructure proposal for Naivasha Special Economic Zone - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 22 | Aecom joins Murphy team to design £340 million Oxford wastewater upgrade - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 23 | PCWA awards $170.5 million contract to build Ophir water treatment plant - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 24 | VINCI Construction wins €192m contract to upgrade wastewater plant in Prague, Czech Republic - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 25 | Mexico relaunches bidding on $840 million Rosarito Desalination Plant after void tender - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 26 | Eight contractors submit bids for Hassyan desalination pipeline works in Dubai - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 27 | U.S. Department of the Interior commits $889 million for western water infrastructure projects - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 28 | ACCIONA secures €44.7 million contract for two key wastewater plants in Madrid - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 29 | Drip irrigation, sun and solar do ‘God’s work’ and a Colombian desert blooms - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 30 | MWSC and Flocean partner to pioneer eco-friendly subsea desalination technology in the Maldives - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 31 | Anglian Water tenders £6 million contract for desalination strategic advisor - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 32 | Kuwait awards $489 million wastewater treatment plant contract to Turkey’s Kuzu - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |
| 33 | Israel launches tender for one of the world’s largest desalination plants in Emek Hefer - Smart Water Magazine / Smart Water Magazine | None None/5 | None / 7.0 | None / None | outside freshness window |

## Known examples: Food production / policy

| Review rank | Title / publisher | Classifier | Region / quality | Recorded metadata / allocation rank | Outcome |
|---:|---|---|---|---|---|
| 1 | Saudi Reef in Jazan: Over SAR1.2 Billion in Support to Boost Production, Empower Beneficiaries - وكالة الأنباء السعودية / Saudi Press Agency | Relevant 5/5 | KSA / 7.0 | 7 / 3 | relevance below 4 |
| 2 | Broad bidirectional effects of global food production on the environment - Nature / Nature | None None/5 | None / 10.0 | None / None | outside freshness window |
| 3 | Civil war hinders crop production and threatens food security in Syria - Nature / Nature | None None/5 | None / 10.0 | None / None | outside freshness window |
| 4 | How to submit \| Food security in sustainable food production - Nature / Nature | None None/5 | None / 10.0 | None / None | outside freshness window |
| 5 | Egypt's minister approves new funding for National Veal Project - Zawya / ZAWYA | Relevant 5/5 | Egypt / 6.0 | 9 / 4 | selected |
| 6 | UAE to grow more food locally under strategy update \| AGBI / AGBI | Relevant 5/5 | UAE / 10.0 | 1 / 1 | selected |
| 7 | UAE targets 50% local crop production under updated Food Security Strategy 2051 - Fast Company Middle East \| The future of tech, business and innovation. / Fast Company Middle East | Relevant 5/5 | UAE / 5.0 | 2 / 4 | selected |
| 8 | Advancing Green Industrialisation in Egypt - SAIIA / saiia.org.za | None None/5 | None / None | None / None | outside freshness window |


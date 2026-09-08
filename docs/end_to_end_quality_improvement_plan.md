# End-to-End Quality and Performance Improvement Plan

## 1. Purpose

This plan improves the quality of the complete local workflow, from source collection to the final Newsletter and Social Media drafts. Editorial quality is the primary objective. Reliability, speed, cost control, explainability, and safe Notion writes support that objective.

The system should consistently:

- Produce eight strong Article Queue choices each week: two Global, two UAE, two KSA, and two Egypt.
- Reject off-mandate, stale, weakly evidenced, and repetitive stories before they reach an editor.
- Preserve source diversity without allowing source reputation to rescue an irrelevant article.
- Learn from human review and previously published newsletters.
- Generate factual, correctly structured Newsletter and Social Media drafts from approved evidence only.
- Select relevant, non-duplicate images with traceable provenance.
- Fail visibly and safely without damaging existing Notion content.

## 2. Current System

The current workflow is functional and its 40 automated tests pass. Its main path is:

```text
Notion Source Registry
  -> RSS / Google News RSS / Website feeds
  -> URL cleanup and URL-hash dedupe
  -> regional quota-led candidate choice
  -> keyword and geography filters
  -> OpenAI enrichment and one relevance gate
  -> Notion Article Queue
  -> human status review
  -> Newsletter and Social Media prompts
  -> Unsplash / Brave image lookup
  -> automation-managed Notion sections
```

This is a good MVP, but the stages optimize locally rather than as one editorial system. The biggest opportunity is to make evidence, ranking, history, and human decisions flow through the entire pipeline.

## 3. Current Weaknesses and Cons

### Critical quality weaknesses

| Weakness | Current behavior | Effect |
| --- | --- | --- |
| Greedy queue admission | `run_daily_ingestion_local.py` chooses a region-filling candidate and then validates it. It never ranks the complete eligible pool. | An early acceptable article can displace a later excellent article. |
| One-dimensional relevance | The LLM returns one `1-5` relevance score, used mainly as a pass/fail threshold. | The score cannot distinguish mandate fit, materiality, regional fit, evidence quality, source quality, freshness, and novelty. |
| Generic company context | The enrichment prompt receives a topic list but no detailed SOMA editorial brief or accepted/rejected examples. | The model cannot reliably distinguish a keyword match from a story useful to SOMA's clients and work. |
| Thin evidence | Enrichment sees a title and feed snippet, not reliable article text or a structured evidence pack. | Scores and summaries are unstable, while a three-paragraph draft invites unsupported elaboration. |
| Broad deterministic filters | Terms such as `water`, `oil`, `gas`, `trade`, and `policy` are enough to pass the first topic filter. | Keyword overlap is mistaken for relevance to SOMA MATER's work. |
| Coarse geography logic | Geography is inferred from short keyword lists. A story is accepted if no known outside location is found. | Unlisted locations and incidental regional mentions are misclassified; `Global` can become a catch-all. |
| URL-only operational dedupe | Queue admission checks canonical URL hashes. `content_hash` is title plus source and is not used for suppression. | Syndicated links, rewritten headlines, and several outlets covering one event can all enter the queue. |
| No editorial memory | Previous newsletters and prior human decisions are not considered. | The workflow can repeat the same event or theme week after week. |
| Quotas can encourage filler | The system keeps looking for a candidate for each regional deficit, but quality is checked only after selection. | Regional balance can dominate editorial quality. |

### Acquisition and source weaknesses

| Weakness | Current behavior | Effect |
| --- | --- | --- |
| Source quality fields are underused | Source Registry `Priority` and `Credibility` mostly affect API provider order, not article ranking. | Trusted, consistently useful sources receive little advantage over weak sources. |
| Source health is inaccurate | `Last Checked` is updated for every active source after a run, including skipped or failed sources. | Notion can report a healthy check when no article was fetched successfully. |
| `Check Frequency` is unused | Every active feed is attempted on every run. | Unnecessary requests and no intentional scheduling by source cadence. |
| Feed fetching is sequential and unbounded | `feedparser` fetches sources one at a time without an explicit per-request timeout, retry policy, ETag, or Last-Modified cache. | A slow source delays the whole run and every run redownloads unchanged feeds. |
| No freshness gate | Old feed entries are not rejected by age before admission. | Stale stories may compete with current-week developments. |
| Google News wrappers remain | URL extraction has fallbacks but cannot consistently recover the publisher URL. | Dedupe, source attribution, evidence extraction, and Newsletter links are weaker. |
| Discovery settings are partly cosmetic | Configured country lists are not used by the current provider clients, and only the first configured language is queried. | The actual search behavior does not fully match `.env`; Arabic coverage is effectively absent. |
| Top-up stops too early | A regional provider top-up is attempted once for a deficit state. If those candidates fail relevance checks, the same deficit is not searched again. | A region can remain underfilled despite available provider budget. |
| Live unscored bypass | `--no-enrich` can write queue items using only broad deterministic filters. | A diagnostic option can create a materially lower-quality live queue. |

### HITL and drafting weaknesses

| Weakness | Current behavior | Effect |
| --- | --- | --- |
| Human intent is reduced to status | Approval and rejection are read, but no reason, rank, or editor preference is captured. | The system cannot learn why stories were rejected or which approved story should lead. |
| Featured story selection ignores editor order | Up to three approved stories are sorted by relevance score and title. | The draft can disregard the editor's desired story order. |
| Draft context is too shallow | Draft prompts receive summaries, angles, hooks, topics, regions, score, and one URL. | The model lacks enough grounded facts for the required three article paragraphs plus SOMA perspective. |
| Prompt formatting is not enforced | The prompt requests an exact shape, but output is accepted as arbitrary text. | Paragraph counts, title/image/source order, and source completeness can drift. |
| One large generation call | A whole Newsletter or Social draft is generated in one request. | One malformed story or failed call affects the complete output, and targeted repair is difficult. |
| No factual validator | No post-generation check confirms that numbers, dates, entities, and claims exist in approved evidence. | Fluent but unsupported content can reach Notion. |
| Traceability is incomplete | Existing Article Queue relations to Newsletter and Social Media pages are not populated after generation. | Editors cannot easily trace generated content back to every source queue item. |

### Image, state, and operational weaknesses

| Weakness | Current behavior | Effect |
| --- | --- | --- |
| Image selection takes the first usable result | Search result metadata is not scored against the story. | Images may be generic or only loosely related. |
| Duplicate detection is run-local | Normalized image URLs are compared within one draft, but provider asset IDs and cross-edition history are not used. | A previous edition's photo can be reused unintentionally. |
| Image provenance is incomplete | The cache stores URL and provider only. | Photographer, provider asset ID, source page, and attribution are lost. |
| Brave image fallback has no rights gate | Any returned image URL can be selected. | Usage rights and origin can be unclear. |
| JSON state writes are not atomic | Seen articles and image assets overwrite JSON files directly. | A failed or interrupted write can corrupt local state. |
| Notion draft replacement deletes first | The old generated section is archived before the replacement is appended and verified. | An API failure can remove the last good draft. |
| Dry-run does not mirror live selection | Dry-run starts region counts at zero and skips current-week page lookup. | A successful preview can differ materially from the live run. |
| Full database scans grow over time | Dedupe pruning reads the entire Article Queue; edition numbering reads all Newsletters. | Runtime and Notion API usage increase with history. |
| No run identity or quality report | Logs and counters are printed, but candidate scores, rejection reasons, timings, provider use, and model/prompt versions are not persisted. | Regressions are hard to diagnose or compare. |
| Tests cover helpers, not the workflow | The 40 passing tests are mostly utility and selection-unit tests. | Provider failures, Notion partial writes, prompt schema drift, and complete dry-run behavior are not protected. |
| Dead configuration remains | SerpAPI is implemented but inactive; `UNSPLASH_SECRET_KEY` is loaded but unused. | Setup is harder to understand and maintain than necessary. |

## 4. Design Principles

1. Quality before quota: satisfy regional targets by widening discovery, never by lowering editorial standards.
2. Rank before write: score the complete bounded candidate pool and write only final winners to Notion.
3. Evidence before prose: build verified evidence packs before enrichment or drafting.
4. Human decisions are data: approval, order, and rejection reason should improve future selection.
5. Notion remains the editorial source of truth: local state stores machine history and caches, not a competing editorial workflow.
6. Deterministic structure, generative language: code controls article count, order, paragraph placement, sources, images, and Notion blocks; the LLM controls wording within validated fields.
7. Safe reruns: every external write is idempotent, recoverable, and associated with a run ID.
8. Bounded complexity: no vector database, workflow orchestrator, web dashboard, or extra cloud service until measured evidence justifies one.

## 5. Target End-to-End Flow

```text
1. Preflight and schema validation
2. Due-source selection and bounded concurrent collection
3. URL resolution, date normalization, and deterministic cleanup
4. Cheap mandate/geography/freshness gate
5. Same-event and historical duplicate detection
6. Bounded regional shortlist
7. Full-text extraction for shortlisted candidates
8. Structured LLM scoring against the SOMA editorial brief
9. Global ranking with regional, source, and event constraints
10. Write eight explained choices to Article Queue
11. Sync HITL status, rejection reason, and editorial rank
12. Build approved story evidence packs and supporting-source sets
13. Generate structured story drafts and validate every field
14. Select relevant, unique, traceable images
15. Render deterministic Notion blocks and safely replace sections
16. Persist outcomes, metrics, prompt versions, and story memory
```

## 6. Core Improvement Specifications

### 6.1 Source acquisition and health

- Fetch feed bytes with `httpx`, using explicit connect/read timeouts, two bounded retries, and conditional requests with ETag and Last-Modified. Pass the returned bytes to `feedparser`.
- Use bounded concurrency, initially six simultaneous feeds. Keep provider API concurrency lower and respect request budgets.
- Apply `Check Frequency` when deciding which sources are due. A manual `--all-sources` override should remain available for health tests.
- Track each source outcome independently: attempted, successful, unchanged, empty, skipped, parse error, HTTP error, and duration.
- Keep `Last Checked` as last attempt. Add only `Last Outcome` and `Last Error` to Source Registry if editors need health inside Notion; keep detailed history local.
- Resolve redirects and Google News links before hashing. Store both original and canonical publisher URLs.
- Reject items without a usable URL, title, publication date, or sufficient evidence unless an explicit fallback rule applies.
- Start with a seven-day freshness window and allow a clearly labeled exception for strategic follow-ups. Make the window a runtime setting, not a prompt decision.
- Query every configured language that the provider actually supports. Use provider country controls only where the API supports them; remove settings that cannot affect behavior.
- Continue regional top-up searches until two qualified articles exist, the request budget is exhausted, or providers return no new candidates. A rejected top-up must not consume a regional slot.
- Keep `--no-enrich` read-only for diagnostics. Live queue writes must always pass the structured quality gate.

### 6.2 Editorial brief and evidence

Create one versioned `soma_editorial_brief.txt` containing:

- SOMA MATER's services, sectors, clients, and decision-making perspective.
- Core themes and strong positive examples.
- Explicit exclusions and strong negative examples, including local stories outside the target geography.
- A precise definition of Global: systemically important across markets or directly relevant to SOMA's mandate, not merely outside UAE, KSA, or Egypt.
- Preferred story types: policy shifts, investment, infrastructure, supply risk, regulation, market structure, resilience, and material operational developments.
- Weak story types: generic corporate PR, lifestyle, local incidents without wider implications, broad politics, and keyword-only matches.

For shortlisted candidates, extract a bounded article body with `trafilatura`, the only proposed new runtime dependency. Do not attempt paywall bypasses. Build an `EvidencePack` with:

- Canonical title, publisher, publication timestamp, and canonical URL.
- Five to ten factual bullets, each derived from the source text.
- Important numbers, dates, organizations, locations, and named projects.
- Directly supported implications, kept separate from reported facts.
- Extraction quality and confidence.
- Up to two corroborating URLs from the candidate's same-event cluster.

Full article text can be transient. Persist the evidence pack and a content fingerprint, not an unnecessary archive of publisher content.

### 6.3 Candidate scoring and selection

Replace `relevance_score` as the decision mechanism with validated sub-scores normalized to `0.0-1.0`:

| Component | Initial weight | Meaning |
| --- | ---: | --- |
| Editorial mandate fit | 30% | Direct fit with SOMA's work and editorial purpose. |
| Strategic materiality | 20% | Policy, commercial, infrastructure, supply, or risk significance. |
| Regional fit | 15% | Strength and usefulness of the Global/UAE/KSA/Egypt connection. |
| Novelty | 15% | Difference from recent queued, approved, and published stories. |
| Source quality | 10% | Bounded trust bonus from Source Registry and observed outcomes. |
| Evidence completeness | 5% | Sufficiency and clarity of extractable facts. |
| Freshness | 5% | Timeliness within the current editorial window. |

`queue_score = weighted sum of the seven components`

Hard gates apply before ranking:

- Editorial mandate fit must be at least `0.70`.
- Regional fit must be at least `0.65` for its assigned bucket.
- Evidence completeness must be at least `0.50`.
- The article must be within the freshness policy or be marked as a material follow-up.
- A same-event duplicate cannot enter beside the selected representative.
- Low-trust or unknown sources require corroboration and cannot pass on score alone.

The thresholds and weights are initial calibration values. Change them only against the labeled evaluation set and recorded HITL outcomes.

Selection must operate on the complete scored pool:

- Shortlist the six strongest metadata candidates per region. If quality gates leave a shortage, score the next candidates in small batches, with a default ceiling of eight scored candidates per region.
- Choose exactly two qualified candidates for each of Global, UAE, KSA, and Egypt.
- Permit at most two queue items from one source and one from one event cluster.
- Use source diversity as a set-level constraint, not a substitute for relevance.
- If fewer than two qualified items exist for a region, mark the run incomplete and report the shortage. Never insert filler or silently relax a hard gate.
- Default `MAX_ARTICLES_PER_RUN` to eight when all weekly deficits are empty at the start of a fresh week. Do not add two generic items merely because the old default is ten.

Source weight should remain deliberately small:

- Manual component: normalized `Priority` and `Credibility` from Source Registry.
- Observed component: smoothed historical rate of articles judged editorially relevant, used only after enough reviews exist.
- Cap the total source contribution at 10% so an on-brand source cannot rescue an off-mandate story.

### 6.4 Duplicate and historical story memory

Use three layers:

1. Exact duplicate: canonical URL and normalized URL hash.
2. Same-event duplicate: normalized headline tokens, organizations, locations, dates, named projects, and the LLM event signature.
3. Historical repetition: local TF-IDF similarity against the last 26 weeks of approved and published story summaries and event signatures.

Start with local TF-IDF and event features. Do not add embeddings or a vector database until evaluation shows that lexical similarity misses an unacceptable number of repeats.

Keep the best article in a same-event cluster as the queue representative. Other reliable articles in that cluster become supporting sources for the evidence pack instead of competing queue entries.

### 6.5 Local state

Replace growing JSON files with one standard-library SQLite database at `.local_state/workflow_state.sqlite3`. It should contain only operational data:

- Run records, stage timings, prompt/model versions, and final outcome.
- Source attempts, HTTP cache metadata, and health history.
- Candidate hashes, event signatures, scores, and rejection reasons.
- Approved/published/rejected story memory synced from Notion.
- Image provider asset IDs, URLs, attribution, and edition usage.

Use transactions, schema versioning, and a one-time import of `seen_articles.json` and `article_assets.json`. Notion remains authoritative for statuses, page content, relations, and editor decisions.

### 6.6 HITL feedback

Keep the existing approval statuses and add the minimum information required to preserve editor intent:

- `Editorial Rank` number: explicit story order for Newsletter and Social drafting.
- `Review Reason` select: `Off mandate`, `Low importance`, `Duplicate`, `Weak evidence`, `Wrong region`, `Stale`, or `Good but not selected`.
- `Queue Score` number and `Selection Reason` rich text for explainability.

Do not add every sub-score to Notion. Keep detailed score components in SQLite and expose only the information useful to an editor.

At ingestion start and before draft generation, sync changed Article Queue outcomes into local story memory. Source performance and ranking calibration should use these outcomes only after enough examples exist; avoid overreacting to one week.

Draft story order must use `Editorial Rank` first, then `Queue Score`, then title as a stable final tie-breaker. Approval status must never be reinterpreted from the model score.

### 6.7 Newsletter and Social Media generation

Generate structured content per story, not one free-form document. A Newsletter story object should contain:

- Headline.
- One or two approved tags.
- Exactly three body paragraphs.
- Exactly one SOMA perspective paragraph.
- Canonical primary and supporting source URLs.
- Image search concept.

The three body paragraphs should be generated from the evidence pack:

1. What happened and why it matters now.
2. Supported operational, policy, commercial, or infrastructure implications.
3. Supported regional, market, or systems context.

The SOMA perspective may interpret the evidence through the editorial brief, but it must not add facts. Generate the Newsletter opening after the stories so it can accurately frame the selected themes.

Social content should use the same evidence packs but a separate structured schema. It should not be a shortened copy of the Newsletter. Preserve the current concise briefing/script voice.

Validate before any Notion write:

- Correct story count and editor-defined order.
- Exact `3 + 1` Newsletter paragraph structure.
- No empty required fields or duplicate sections.
- Every source is an approved canonical URL; no Google News wrapper remains.
- Every number, date, and named project in prose exists in the evidence pack.
- No URL or claim from one story appears under another story.
- Title, tags, image, body, SOMA perspective, and sources occur in the required order.
- Output stays within configured length bounds.

Allow one targeted repair attempt for a failed story object. If it still fails, leave the current Notion draft untouched and report the exact validation errors.

Render Notion blocks directly from validated story objects. Do not parse model-authored markdown to determine structural placement.

### 6.8 Images

- Use Unsplash first and Brave only as a controlled fallback, matching the current product decision.
- Generate short visual concepts from each approved evidence pack rather than searching the complete headline.
- Rank image results by topic match, region match when visually meaningful, landscape suitability, minimum dimensions, and result metadata.
- Store the Unsplash photo ID or normalized provider asset ID, provider page, image URL, photographer/credit, dimensions, and edition usage.
- Reject an asset ID already used in the current edition or recent edition history. Continue using normalized URL identity as a second exact check.
- Validate that the image URL resolves and is an image before drafting.
- For Brave fallback, retain the result page and origin. If provenance or acceptable use is unclear, publish no image and flag it for HITL instead of choosing blindly.
- Keep the title above the image and the image above paragraph one through deterministic block rendering.
- Add perceptual hashing only if provider asset IDs and normalized URLs still allow meaningful duplicate-image failures. It is not part of the first implementation.

### 6.9 Safe Notion writes and reruns

- Validate all required databases and property types during preflight before collection or generation.
- Give each run a UUID and include it in local records and automation markers.
- For generated sections, append a complete new pending section, verify its block count and markers, then archive the previous section. If append or verification fails, archive the pending blocks and preserve the old section.
- Update Newsletter/Social statuses only after validation and verified content replacement.
- Populate the existing Article Queue relations to the Newsletter and Social Media pages for every used article.
- Detect duplicate weekly pages and fail with their IDs instead of silently selecting the first.
- Query current-week or sorted recent records instead of scanning complete Notion databases.
- Make dry-run execute the same reads, scoring, ranking, and validation as live mode, skipping only writes. Its region counts and deficits must match a live run at the same moment.
- Add `--week-start YYYY-MM-DD`, `--newsletter-only`, `--social-only`, and `--explain` controls so historical reruns and focused corrections are first-class operations.

## 7. Implementation Roadmap

### Phase 0: Baseline and editorial contract

Deliverables:

- Add `soma_editorial_brief.txt` with accepted/rejected examples from real past work.
- Create a labeled benchmark of at least 60 candidate articles, balanced across four regions and including known bad cases such as keyword-matching local stories outside the target area.
- Capture three to five strong human Newsletter/Social examples as structural and voice references.
- Add a read-only run report with funnel counts, rejection reasons, source yield, regional coverage, provider calls, timings, and prompt/model hashes.

Exit criteria:

- Current pipeline has a recorded baseline on the benchmark.
- Editorial fit and region labels have human ground truth.
- Future prompt or scoring changes can be compared before live writes.

### Phase 1: Acquisition, evidence, and state foundation

Deliverables:

- Implement bounded HTTP feed fetching, timeout/retry behavior, conditional requests, freshness filtering, and accurate per-source outcomes.
- Resolve publisher URLs before dedupe.
- Add bounded full-text extraction and `EvidencePack` creation for shortlisted candidates.
- Add SQLite state with migrations and import existing JSON state.
- Make dry-run use current live region counts without writing.

Exit criteria:

- One failed source cannot delay or misreport the run.
- Stale stories and unresolved wrapper links do not enter scoring.
- Every scored candidate has an evidence quality value and traceable canonical URL.
- Interrupted state writes cannot corrupt the store.

### Phase 2: Queue quality engine

Deliverables:

- Replace the single enrichment score with structured score components and validation.
- Implement deterministic prefilters, same-event clustering, local historical novelty, bounded source weight, and score-all-then-select admission.
- Make fallback discovery iterative and regional until qualified coverage or budget exhaustion.
- Write final queue pages only after all eight winners are determined.
- Persist concise selection and rejection explanations.

Exit criteria:

- At least 90% of admitted benchmark articles are human-labeled on-mandate.
- Region assignment is at least 95% accurate on the benchmark.
- No same-event cluster contributes more than one queue choice.
- Queue ordering is invariant to feed input order.
- Missing regional coverage produces an explicit incomplete result, never filler.

### Phase 3: HITL memory and calibration

Deliverables:

- Add `Editorial Rank`, `Review Reason`, `Queue Score`, and `Selection Reason` to the live Article Queue after schema approval.
- Sync Notion outcomes and published story memory into SQLite.
- Add smoothed source performance and 26-week novelty to scoring.
- Produce a weekly quality report comparing selections, rejections, source yield, and repeat themes.

Exit criteria:

- Newsletter/Social story order matches editor ranking.
- Every rejected reviewed article can carry a reason.
- Previously published same-event stories are blocked or clearly marked as material follow-ups.
- Source weighting changes gradually and cannot exceed its 10% cap.

### Phase 4: Grounded drafts and image quality

Deliverables:

- Generate per-story structured Newsletter and Social objects from evidence packs.
- Add deterministic structural and factual validators with one targeted repair.
- Render Notion blocks directly from validated objects.
- Upgrade image selection, provenance storage, recent-use dedupe, URL validation, and no-image fallback.
- Link used Article Queue pages to generated Newsletter/Social pages.

Exit criteria:

- Every Newsletter story has exactly three evidence-based body paragraphs plus one SOMA perspective paragraph.
- All numeric claims and source URLs pass deterministic validation.
- Title, tags, image, body, SOMA perspective, and sources are always in the required order.
- No duplicate image asset appears within an edition or the configured recent-use window.
- Editors rate factual grounding and voice at least 4/5 across three consecutive drafts.

### Phase 5: Safe writes, performance, and cleanup

Deliverables:

- Implement append-verify-swap Notion writes and failure cleanup.
- Add schema preflight, duplicate-week detection, scoped Notion queries, retries with jitter, and run IDs.
- Add focused CLI controls for week and output type.
- Remove SerpAPI client/config and the unused Unsplash secret unless a measured need returns.
- Close provider clients cleanly and record stage latency and request counts.

Exit criteria:

- Injected Notion failures never remove the last valid generated draft.
- Rerunning the same week creates no duplicate pages, queue records, managed sections, or relations.
- Dry-run winners match live-run winners when external inputs are unchanged.
- The full run remains within configured API budgets and has no unexplained full-database scans.

## 8. Quality Scorecard

Use a compact weekly scorecard instead of a dashboard:

| Area | Metric | Initial target |
| --- | --- | ---: |
| Queue | Human-labeled on-mandate precision | >= 90% |
| Queue | Correct regional assignment | >= 95% |
| Queue | Same-event duplicates | 0 per week |
| Queue | Qualified regional coverage | 2 per region or explicit shortage |
| Queue | Single-source concentration | <= 2 of 8 |
| Queue | Stale unflagged articles | 0 |
| Sources | Attempts with recorded outcome | 100% |
| Sources | Wrapper URLs in final queue | 0 |
| Draft | Required structure pass rate | 100% |
| Draft | Unsupported numeric/date claims | 0 |
| Draft | Canonical source-link pass rate | 100% |
| Images | Duplicate assets in recent window | 0 |
| Images | Broken image URLs at write time | 0 |
| Operations | Safe rerun/idempotency failures | 0 |
| Operations | Runs with complete persisted report | 100% |
| Efficiency | LLM-scored candidates per normal run | <= 32 |
| Efficiency | Provider requests above configured budget | 0 |

Do not optimize only for the rate at which queued items become Newsletter stories. The queue intentionally presents choices for HITL. Measure whether each choice was genuinely relevant, differentiated, and useful, and use `Good but not selected` to separate quality from final editorial selection.

## 9. Test Strategy

Keep the default suite offline and fast. Add:

- Golden relevance and region tests from the labeled benchmark.
- Input-order invariance and exact `2/2/2/2` constrained-selection tests.
- Same-event, syndicated-title, canonical-URL, and historical-repeat tests.
- Source-priority tests proving source reputation cannot overcome a failed hard gate.
- Feed timeout, malformed feed, unchanged ETag, stale item, and provider-budget tests.
- LLM schema tests for missing, malformed, out-of-range, and prompt-injected fields.
- Draft evidence tests for unsupported numbers, wrong URLs, incorrect order, and incorrect `3 + 1` structure.
- Image tests for reused asset IDs, transformed URLs, failed URLs, provenance, and no-image fallback.
- Fake-Notion integration tests for create/update/relation behavior, pagination, duplicate weeks, and partial append failures.
- End-to-end dry-run fixtures that exercise source input through final ranked report without network or writes.

Live verification should remain deliberate:

1. Run unit and integration tests.
2. Run benchmark evaluation and compare with the saved baseline.
3. Run ingestion dry-run with `--explain` and inspect all eight winners plus near misses.
4. Run queue-only live ingestion.
5. Complete HITL and verify outcome sync.
6. Generate Newsletter-only, inspect structure/facts/images, then generate Social-only.
7. Rerun both outputs and confirm idempotency and manual-content preservation.

## 10. Lean File Plan

Prefer extending cohesive modules over creating one file per small function:

- `models/article.py`: candidate scores, event identity, selection reason, and evidence model.
- `models/draft.py`: structured Newsletter/Social story schemas and validation results.
- `pipeline/collect.py`: due-source scheduling, bounded collection, and source outcomes.
- `sources/rss.py`: byte parsing only; HTTP policy belongs in collection/client code.
- `pipeline/content.py`: canonical resolution, bounded extraction, and evidence-pack creation.
- `pipeline/candidate_selection.py`: deterministic gates, scoring, clustering, novelty, and constrained final selection.
- `pipeline/state.py`: SQLite schema, migrations, transactions, state import, and Notion outcome sync.
- `pipeline/draft.py`: evidence loading, editor-order selection, structured generation, and validation.
- `pipeline/images.py`: visual concepts, ranking, asset history, provenance, and validation.
- `pipeline/notion_write.py`: direct block rendering, append-verify-swap, relations, and run markers.
- `pipeline/evaluation.py`: benchmark metrics and weekly run scorecard.
- `clients/llm_client.py`: provider-native structured output, strict parsing, prompt versions, and targeted repair.
- `scripts/run_daily_ingestion_local.py`: thin orchestration only.
- `scripts/run_weekly_drafts_local.py`: thin orchestration plus week/output flags.

Remove after replacement:

- Greedy admission helpers that select before scoring.
- Inactive `serpapi_client.py` and related settings.
- Unused `UNSPLASH_SECRET_KEY` handling.
- Direct JSON state writes after successful SQLite migration.
- Markdown-dependent Newsletter layout rendering.

## 11. Explicit Non-Goals

The first implementation should not add:

- A vector database or hosted database.
- A web dashboard or workflow orchestrator.
- Model fine-tuning.
- Automatic publishing without HITL.
- A general web crawler or paywall bypass.
- Multiple LLM providers merely for abstraction.
- Perceptual image hashing unless measured duplicate failures remain.
- Dozens of new Notion properties or environment variables.

These can be reconsidered only if the scorecard identifies a concrete limitation.

## 12. Definition of Done

The improvement program is complete when:

- The queue is selected from a fully scored, evidence-backed pool and reliably produces two qualified choices for each target region when the source ecosystem contains them.
- Off-mandate and repetitive items are measurable exceptions, not recurring review work.
- Human approval, rank, and rejection reasons affect future selection without overriding editorial safeguards.
- Newsletter stories consistently meet the required three paragraphs plus one SOMA perspective, with validated facts, canonical sources, correct positioning, and unique images.
- Social content is grounded in the same approved evidence but shaped for its own format.
- Existing Notion drafts survive failures, reruns are idempotent, and every run can be explained from its persisted report.
- The system remains local, understandable, and operable through the existing direct scripts.

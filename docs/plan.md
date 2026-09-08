**Current Weaknesses**
- The queue is admitted greedily, not ranked globally. The live loop picks the next article mainly by weekly region deficit and source cap, then asks “is this acceptable?”, instead of scoring the whole candidate pool and choosing the strongest set. That means a merely-passable `UAE` story can beat a much better one just because it appears earlier. See [run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:169) and [discovery.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/discovery.py:471).
- `relevance_score` is only a gate, not a true ranking signal. Today it mostly decides pass/fail against `MIN_ARTICLE_RELEVANCE_SCORE`; it does not drive the final queue order in a rich way. See [run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:286).
- The LLM judges relevance from thin context. The prompt only sees title, snippet, source labels, and generic company topics; it does not see a real SOMA brief, examples of good/bad articles, or the full article body. See [article_enrichment.txt](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/prompts/article_enrichment.txt:1) and [llm_client.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/clients/llm_client.py:47).
- The deterministic topic filter is too broad. Keywords like `water`, `oil`, `gas`, `trade`, and `policy` can still let in adjacent or weakly related stories before the LLM has a chance to reject them. See [relevance.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/relevance.py:13).
- The geography filter is coarse. It is basically “contains interest geography” or “does not contain obvious outside-interest geography,” which is better than nothing but still weak for nuanced global stories. See [relevance.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/relevance.py:132).
- Source quality metadata is underused. `Source.priority` and `Source.credibility` exist, but they do not materially influence queue admission; they mostly affect provider order for API top-ups. See [source.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/source.py:8) and [discovery.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/discovery.py:121).
- Deduplication is only URL-based for real admission. `content_hash` exists, but it is just `title + source` and is not used to suppress near-duplicates, same-event coverage, or repeats from past newsletters. See [hashing.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/utils/hashing.py:22) and [deduplicate.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/deduplicate.py:10).
- There is no memory of past newsletters. The system cannot tell that this week’s candidate is basically the same storyline you covered three weeks ago.
- Feed data quality limits the model. RSS snippets are often too short or vague, and Google News feeds sometimes leave you with wrapper URLs or weak metadata. See [rss.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/sources/rss.py:20) and [urls.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/utils/urls.py:93).
- The rigid `2 Global / 2 UAE / 2 KSA / 2 Egypt` target can force filler if one bucket is weak that week. The current system tries to solve that with API top-ups, but the structural pressure is still there. See [config.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/config.py:56).
- The system does not learn from your HITL choices. `Use in Newsletter`, `SNS Only`, and `Rejected` are valuable feedback signals, but they are not fed back into ranking.

**Implementation Plan**
1. Redesign relevance into a composite `queue_score`.
   Replace one blunt `relevance_score` with sub-scores: `mandate_fit`, `regional_fit`, `story_importance`, `source_weight`, `novelty`, and `freshness`, plus one final weighted `queue_score`. Keep `relevance_score` if you want it in Notion, but stop relying on it alone.
2. Change admission from “pick then filter” to “score then choose.”
   Collect a candidate pool first, enrich/score the pool, then choose the best articles per weekly region bucket. The weekly quota should shape the final set, not dominate the initial choice. Main files: [run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:63) and [discovery.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/discovery.py:380).
3. Give the model a real SOMA editorial brief.
   Add a structured company-context file describing what SOMA covers, what it explicitly does not cover, preferred story types, target geographies, and 10-20 accepted/rejected examples. Load that into [llm_client.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/clients/llm_client.py:47) and rewrite [article_enrichment.txt](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/prompts/article_enrichment.txt:1) to score against concrete editorial standards.
4. Introduce source weighting without letting it override fit.
   Use `priority` and `credibility` from `Source Registry` as a bonus factor. A strong Reuters/S&P/Zawya article should get a boost, but an off-mandate article should still lose. This belongs in [source.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/source.py:8), [source_registry.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/source_registry.py:16), and the new ranking code.
5. Add historical novelty checks.
   Build a local store of past newsletter story summaries and approved queue entries. Start with TF-IDF similarity because it is simple and cheap. Downrank new candidates that are too similar to recently published stories unless the new one is materially bigger or more strategic.
6. Add same-story clustering before queue admission.
   Group candidates that appear to cover the same event across multiple outlets, then keep the best representative or at most one main article plus one differentiated angle. This will cut noisy duplicates dramatically.
7. Upgrade content extraction for top candidates.
   For the top candidate pool only, fetch publisher page text where possible and score from full text, not just feed snippet. That will help both relevance and summary quality. Keep RSS-only as fallback, but do not let weak snippets be the final truth source.
8. Use HITL outcomes as training data.
   Persist article outcome labels such as `Use in Newsletter`, `SNS Only`, `Rejected`, and maybe manual notes. Then use those labels to calibrate source weights, novelty thresholds, and prompt examples over time.
9. Improve observability.
   For every queued article, store a short machine-readable reason: why it passed, its sub-scores, what region bucket it filled, and what close competitors were rejected. That will make debugging queue quality much easier.
10. Tighten tests around quality, not just utilities.
   Add tests for “off-mandate but keyword-matching” cases, same-event duplicate suppression, regional bucket ranking, source-weight effects, and historical-novelty rejection.

**Recommended Rollout**
1. Phase 1: Better SOMA context + composite scoring + score-then-choose admission.
2. Phase 2: Source weighting + same-story clustering.
3. Phase 3: Historical novelty memory with TF-IDF over past newsletters.
4. Phase 4: Full-text extraction for top candidates.
5. Phase 5: HITL feedback loop and ongoing calibration.

**Concrete File Targets**
- Ranking and admission: [run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:63), [discovery.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/discovery.py:380), [relevance.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/relevance.py:199)
- LLM context and prompts: [llm_client.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/clients/llm_client.py:47), [article_enrichment.txt](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/prompts/article_enrichment.txt:1)
- Models and local state: [article.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/article.py:9), [source.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/source.py:8), [deduplicate.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/deduplicate.py:10), [hashing.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/utils/hashing.py:22)
- Notion writeback and explainability: [notion_write.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/notion_write.py:26)

**Implementation Spec**

**Goal**
Improve `Article Queue` quality so the system picks the strongest, most on-mandate, non-redundant stories for `Global`, `UAE`, `KSA`, and `Egypt`, instead of mostly picking “first acceptable” stories.

**What We’ll Change**
- Move from `threshold-based relevance` to `ranked admission`.
- Add a composite `queue_score`.
- Give the LLM better SOMA context.
- Add source weighting.
- Add novelty / anti-duplication memory.
- Add same-event clustering.
- Add explainability so we can see why an article got in.

---

**1. Current Weaknesses To Fix**
- Admission is greedy:
  See [run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:169). The loop picks a region-filling candidate first, then checks if it is relevant enough.
- Relevance is too one-dimensional:
  `relevance_score` is only `1-5`, and mainly used as a gate. See [article_enrichment.txt](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/prompts/article_enrichment.txt:1).
- SOMA context is too thin:
  The model only sees generic `company_topics`, not a real editorial brief. See [llm_client.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/clients/llm_client.py:47).
- Topic filtering is broad:
  Some keywords in [relevance.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/relevance.py:13) are too permissive.
- Geography filtering is coarse:
  It is mostly inclusion/exclusion keyword logic. See [relevance.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/relevance.py:236).
- Source metadata is underused:
  `priority` and `credibility` are loaded but barely affect ranking. See [source_registry.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/source_registry.py:40).
- Deduplication is weak:
  `content_hash` is just normalized `title + source` and is not used as a ranking or suppression feature. See [hashing.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/utils/hashing.py:22).
- No memory of past newsletters:
  The system cannot downrank “we basically covered this already”.
- No HITL learning loop:
  `Use in Newsletter` / `Rejected` are not reused to improve future ranking.

---

**2. New Ranking Model**
Replace “minimum relevance only” with a weighted score:

`queue_score = 0.35 * mandate_fit + 0.20 * regional_fit + 0.15 * story_importance + 0.10 * source_weight + 0.10 * novelty + 0.10 * freshness`

All components normalized to `0.0 - 1.0`.

**Definitions**
- `mandate_fit`
  How directly the story matches SOMA’s actual work and editorial scope.
- `regional_fit`
  How strongly the story matches `Global`, `UAE`, `KSA`, or `Egypt` in a useful way.
- `story_importance`
  Whether it has strategic, policy, commercial, infrastructure, or market significance.
- `source_weight`
  Bonus from source quality and priority, never enough to rescue a weak article.
- `novelty`
  Penalty if the story is too similar to recent approved/published stories.
- `freshness`
  Slight bonus for timely stories inside the current window.

**Important rule**
- `mandate_fit` and `regional_fit` are hard filters first.
- `source_weight` can boost a good story, but must never override weak fit.

---

**3. New Structured LLM Output**
Expand `EnrichedArticle` from one relevance score to a richer payload.

**New fields for `EnrichedArticle`**
In [article.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/article.py:30):
- `summary`
- `why_it_matters`
- `mandate_fit_score: int`
- `regional_fit_score: int`
- `story_importance_score: int`
- `relevance_score: int`
  Keep for compatibility, but compute from sub-scores.
- `topic: list[str]`
- `region: list[str]`
- `newsletter_angle`
- `sns_hook`
- `reason_for_inclusion: str`
- `reason_for_rejection: str`
- `primary_region: str`
- `event_signature: str`
  Short LLM-generated phrase like “Bahrain desalination expansion via Acwa”.

**LLM scoring scale**
Use `1-5` for sub-scores, then normalize.

---

**4. New Deterministic Pre-LLM Signals**
Before we call OpenAI, compute stronger local features.

**New local article features**
In [article.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/article.py:9):
- `source_priority: str`
- `source_credibility: str`
- `matched_topics: list[str]`
- `detected_primary_region: str`
- `deterministic_mandate_fit: float`
- `deterministic_regional_fit: float`
- `full_text: str`
  Empty at first, later used in Phase 4.
- `queue_score: float`
- `novelty_score: float`
- `source_weight_score: float`

**Source weight mapping**
- `Core = 1.0`
- `Secondary = 0.8`
- `Trial = 0.6`

**Credibility mapping**
- `High = 1.0`
- `Medium = 0.8`
- `Low = 0.6`

Then:
`source_weight_score = 0.7 * priority_score + 0.3 * credibility_score`

---

**5. New Admission Logic**
Replace the current “pick candidate, then filter it” loop with this:

1. Collect all raw candidates.
2. URL dedupe.
3. Compute deterministic features.
4. Suppress obvious off-mandate / outside-scope candidates.
5. Enrich a bounded candidate pool with OpenAI.
6. Compute final `queue_score` for every remaining candidate.
7. Cluster near-duplicate stories.
8. Select final set per region:
   - choose top `2` for `Global`
   - top `2` for `UAE`
   - top `2` for `KSA`
   - top `2` for `Egypt`
9. If a region is short:
   - call fallback providers
   - score those candidates the same way
   - fill the missing slots
10. Write only final winners to Notion.

This is the most important architectural shift.

---

**6. Novelty / Historical Memory**
Start simple with TF-IDF, not embeddings.

**New local store**
Add `.local_state/newsletter_memory.json`

Each record:
- `id`
- `week_start`
- `week_end`
- `title`
- `summary`
- `newsletter_angle`
- `topic`
- `region`
- `source_name`
- `canonical_url`
- `status`
  Approved / Published / Rejected
- `event_signature`

**Novelty scoring**
For each new candidate:
- compare against recent `Published` and `Use in Newsletter` memory
- compare title + summary + event_signature
- if similarity is high, apply novelty penalty
- if it is clearly a bigger follow-up, reduce penalty rather than rejecting it

**Phase 1 implementation**
- TF-IDF over stored text fields
- cosine similarity threshold:
  - `> 0.85` likely same story
  - `0.70 - 0.85` likely same theme / adjacent repeat

Later, embeddings can replace this if needed.

---

**7. Same-Event Clustering**
Create one more suppression layer inside a single run.

**Logic**
- Group candidates by:
  - canonical host
  - title similarity
  - event_signature similarity
  - overlapping named entities / keywords
- Keep one primary article per cluster:
  - highest `queue_score`
- Allow a second story from the same cluster only if:
  - different region angle
  - materially new policy/commercial detail
  - different editorial use case

This prevents “3 outlets covering the same Acwa project” from flooding the queue.

---

**8. Better SOMA Context**
Add a real editorial brief file.

**New prompt file**
Create:
- [soma_editorial_brief.txt](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/prompts/soma_editorial_brief.txt)

Contents:
- what SOMA covers
- what SOMA does not cover
- preferred story types
- examples of strong queue candidates
- examples of weak queue candidates
- how to interpret “Global” vs `UAE/KSA/Egypt`
- how to treat general politics, generic macro, corporate PR, lifestyle, consumer tech

Then load this in [llm_client.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/clients/llm_client.py:47) and prepend it in enrichment prompts.

---

**9. Recommended Notion Additions**
Optional, but useful for debugging.

**Article Queue new properties**
- `Queue Score` number
- `Mandate Fit` number
- `Regional Fit` number
- `Story Importance` number
- `Novelty Score` number
- `Primary Region` select
- `Selection Reason` rich_text
- `Rejection Reason` rich_text
- `Event Signature` rich_text

If you want to keep Notion light, only add:
- `Queue Score`
- `Primary Region`
- `Selection Reason`

---

**10. File-by-File Change Plan**

**Phase 1: Better scoring and admission**
- [src/research_automation/models/article.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/article.py:9)
  Add new candidate scoring fields.
- [src/research_automation/prompts/article_enrichment.txt](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/prompts/article_enrichment.txt:1)
  Expand JSON schema and stricter editorial rules.
- `src/research_automation/prompts/soma_editorial_brief.txt`
  New SOMA-specific context file.
- [src/research_automation/clients/llm_client.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/clients/llm_client.py:47)
  Load new brief; parse richer JSON output.
- [src/research_automation/pipeline/relevance.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/relevance.py:199)
  Add deterministic `mandate_fit` and `regional_fit` helpers.
- [src/research_automation/pipeline/discovery.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/discovery.py:380)
  Replace greedy prioritization with scored candidate ranking.
- [scripts/run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:63)
  Orchestrate score-all-then-select flow.

**Phase 2: Source weighting**
- [src/research_automation/models/source.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/models/source.py:8)
  No schema change needed; use existing fields.
- [src/research_automation/pipeline/source_registry.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/source_registry.py:16)
  Ensure normalized source weight metadata.
- New helper:
  - `src/research_automation/utils/source_scoring.py`

**Phase 3: Novelty and memory**
- New file:
  - `src/research_automation/pipeline/newsletter_memory.py`
- New local state:
  - `.local_state/newsletter_memory.json`
- New helper:
  - `src/research_automation/utils/similarity.py`
- Update:
  - [scripts/run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:63)
  - [scripts/run_weekly_drafts_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_weekly_drafts_local.py:1)
  So published stories get written into memory.

**Phase 4: Same-event clustering**
- New file:
  - `src/research_automation/pipeline/clustering.py`
- Update:
  - [scripts/run_daily_ingestion_local.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/scripts/run_daily_ingestion_local.py:63)

**Phase 5: Notion explainability**
- [src/research_automation/pipeline/notion_write.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/src/research_automation/pipeline/notion_write.py:26)
  Write extra score/reason fields if present.

---

**11. Proposed Selection Formula**
Use this exact first version:

- `mandate_fit = llm.mandate_fit_score / 5`
- `regional_fit = llm.regional_fit_score / 5`
- `story_importance = llm.story_importance_score / 5`
- `source_weight = computed locally`
- `novelty = 1 - similarity_penalty`
- `freshness = freshness_from_published_date`

Final:
`queue_score = 0.35*mandate_fit + 0.20*regional_fit + 0.15*story_importance + 0.10*source_weight + 0.10*novelty + 0.10*freshness`

**Hard filters**
Reject if any of these are true:
- `mandate_fit_score <= 2`
- `regional_fit_score <= 2`
- outside-interest geography flag triggered
- same-story similarity above hard threshold and not a clear follow-up
- source is low trust and score is borderline

---

**12. Minimal New Tests**
Add tests for:
- same topic keyword but off-mandate article gets low `mandate_fit`
- strong Reuters/S&P article beats weaker same-region article from lower source
- near-duplicate articles cluster together
- prior newsletter similarity penalizes repeated theme
- region quotas still fill exactly `2/2/2/2`
- scored selection beats greedy ordering in a crafted fixture

Likely files:
- `tests/test_queue_scoring.py`
- `tests/test_novelty.py`
- `tests/test_clustering.py`
- extend [tests/test_relevance.py](/C:/Users/mabaan/Documents/github/Notion-Workflow/tests/test_relevance.py:1)

---

**13. Verification Order**
1. `pytest`
2. dry-run ingestion on empty queue
3. inspect scored candidates before write
4. live ingestion to queue only
5. compare accepted vs rejected articles manually
6. tune weights
7. only then keep the changes

---

**14. Recommended Build Order**
1. Better SOMA prompt context
2. Richer LLM output with sub-scores
3. Composite `queue_score`
4. Score-then-select admission loop
5. Source weighting
6. TF-IDF newsletter memory
7. Same-event clustering
8. Optional Notion debug fields

**Working Context**
- Repo: [Notion-Workflow](C:/Users/mabaan/Documents/github/Notion-Workflow)
- CWD: `C:\Users\mabaan\Documents\github\Notion-Workflow`
- Date: `2026-07-11`
- Timezone: `Asia/Dubai`
- Active file: [.env](/C:/Users/mabaan/Documents/github/Notion-Workflow/.env)

**Project Understanding**
- This is a local-only Python workflow using Notion as the source of truth.
- Main flow:
  - ingest articles into `Article Queue`
  - enrich with OpenAI
  - human approves/rejects in Notion
  - generate Newsletter and SNS drafts
- Current weekly queue target is:
  - `Global=2`
  - `UAE=2`
  - `KSA=2`
  - `Egypt=2`

**Current Queue Logic I’m Assuming**
- Load only `Active = true` sources from `Source Registry`
- Collect only from `RSS`, `Google News RSS`, and `Website`
- Dedupe with `.local_state/seen_articles.json`
- Filter by:
  - company-topic match
  - geography-of-interest match
  - LLM relevance threshold
- Cap per source:
  - `MAX_ARTICLES_PER_SOURCE_PER_RUN=2`
- Weekly balancing happens before final write

**Recent Changes Already Made**
- Newsletter prompt now forces:
  - `3` article paragraphs
  - `1` `SOMA's Perspective` paragraph
- Newsletter image placement fixed to:
  - `title -> tags -> image -> body -> SOMA para -> sources`
- Live newsletter and SNS generation were both run successfully.
- I also produced a detailed improvement plan for queue quality and relevance.

**Current Weak Spots I’m Tracking**
- Relevance scoring is still too weak as a ranking signal.
- Admission is still too greedy / region-first.
- Source quality is underused.
- No strong historical novelty check yet.
- `content_hash` is too shallow for semantic dedupe.
- The model still lacks a richer SOMA editorial brief.

**What I Believe You Want Next**
- Turn the queue-quality plan into actual implementation work, starting with Phase 1:
  - richer SOMA context
  - better scoring
  - score-then-select queue admission

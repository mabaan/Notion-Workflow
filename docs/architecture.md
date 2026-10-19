# Architecture

`scripts/run_daily_ingestion_local.py` runs the workflow only as far as Article
Queue. `pipeline/ingestion.py` coordinates the following modules:

1. `source_registry.py` validates and sorts publisher/provider records;
   `source_health.py` handles scheduling and records actual source attempts.
2. `selection.py` loads current Dataset Meeting region, publisher, URL and event
   state. Remaining weekly capacity bounds the run before collection or paid work.
3. `sources/rss.py` and `collect.py` fetch due RSS feeds with bounded concurrency,
   retries and deterministic ordering.
4. In `ARTICLE_SELECTION_MODE=luna`, `article_classification.py` applies objective
   prechecks, `clients/article_classifier.py` classifies all eligible metadata in
   bounded batches, and `luna_selection.py` merges results and allocates enrichment.
   In the default `deterministic` mode, `candidate_ranking.py` performs the existing
   keyword/geography screening and regional shortlisting.
5. `article_retrieval.py` retrieves evidence at allocated enrichment opportunities.
   Optional `google_news_resolver.py` resolves wrappers immediately before this
   retrieval. `clients/llm_client.py` performs the existing detailed enrichment.
6. `discovery.py` invokes configured Brave/NewsAPI providers for remaining shortages
   under their request limits. A matched registered publisher supplies source
   quality; discovery-provider quality orders provider use only.
7. `selection.py` selects strict winners, then eligible Luna fallback winners from
   already-enriched candidates. It applies coverage preferences, final scores,
   publisher caps, exact/canonical URL exclusions and deterministic event matching.
8. `notion_write.py` creates complete final-winner pages. `deduplicate.py` records
   a processed URL only after the page is created successfully. `candidate_audit.py`
   writes local diagnostics for both live runs and dry runs.

The final queue score is unchanged:

```text
100 * (0.70 * relevance/5 + 0.20 * editorial_significance/5 + 0.10 * editorial_quality/10)
```

Unknown publisher quality contributes zero. Strict relevance is at least 4 for
registered publishers and 5 for unregistered publishers. Luna fallback requires
a registered publisher and both final relevance and significance of at least 3,
plus all other publication and selection constraints.

Regional targets default to Global 3, UAE 4, KSA 3 and Egypt 2. Luna permits quality
overflow between regions within the shared weekly total of 12. Deterministic mode
retains regional ceilings and strict-only selection. Both modes respect existing
weekly state, the per-run maximum and the weekly publisher cap of two.

An optional direct-site discovery supplement is restricted to shadow dry runs.
Google News resolution is independent and default-off. See
[Luna selection](luna_selection.md), [resolver details](google_news_resolution.md)
and [direct-site discovery](hybrid_discovery.md).

Newsletter/social generation is a separate command. It reads human-approved
Article Queue items and uses existing evidence, image handling and draft validation.
Generated files are local artifacts under ignored `.preview/`; persistent URL and
image state lives in ignored `.local_state/`.

## Feed-provided evidence

RSS `content:encoded` or equivalent article content can supply evidence before a
publisher-page request. Cleaned content must have at least 300 characters, is
limited to 12,000 characters and uses a 2 MB input ceiling. Its `feed_content`
status explicitly means completeness is unverified: the feed may contain only
an excerpt. Descriptions alone are not article evidence. Missing, short or
oversized feed content follows the existing publisher-retrieval/snippet fallback.
Research Notes retain concise factual points and the limitation, rather than
storing the full article body in Notion.

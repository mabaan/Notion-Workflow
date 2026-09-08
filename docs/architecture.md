# Architecture

The daily ingestion entry point is intentionally thin. `pipeline/ingestion.py` coordinates these focused modules:

1. `pipeline/source_registry.py` validates the revised live schema, parses typed source fields, and sorts sources explicitly rather than trusting Notion row order.
2. `pipeline/source_health.py` applies Daily, Weekly, and On Demand scheduling and writes health only for actual source attempts.
3. `sources/rss.py` fetches bytes with explicit timeouts, redirects, and at most two retries. `pipeline/collect.py` runs up to six feeds concurrently and sorts the combined result deterministically.
4. `pipeline/candidate_ranking.py` normalizes candidates, applies deterministic eligibility gates, builds source-diverse shortlists, enriches at most eight candidates per deficient region, and calculates the transitional score.
5. `pipeline/selection.py` loads current weekly region/publisher/event state and selects from the complete scored pool under exact quotas, a hard publisher cap, and deterministic same-event suppression.
6. `pipeline/discovery.py` orders provider rows by their own Editorial Quality and uses providers only for remaining regional shortages. A discovered result inherits quality only from a matched Publisher row.
7. `pipeline/notion_write.py` creates only final winners and includes completed enrichment in the initial page payload.
8. `pipeline/deduplicate.py` records a URL only after its Notion page was created successfully.

The queue score is:

```text
100 * (0.90 * relevance/5 + 0.10 * editorial_quality/10)
```

Unknown publisher quality contributes zero. Provider quality affects invocation order only. Headline event matching uses normalized title-token Jaccard similarity with a threshold of `0.72`; the implementation is isolated in `pipeline/selection.py` for later replacement.

Newsletter and Social Media generation are outside this selection pipeline and remain unchanged.

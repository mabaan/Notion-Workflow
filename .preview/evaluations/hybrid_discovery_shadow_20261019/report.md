# Four-source supplemental shadow implementation

Implemented only the default-off discovery supplement. No production feed is replaced. DIRECT_SITE_DISCOVERY_ENABLED=true requires --dry-run; live use is rejected before external activity. No live discovery, paid model requests, Notion writes or ingestion-state writes were performed during implementation.

## Exact behavior

Configured feeds collect as before. For due active Arab News, Saudi Gazette, Khaleej Times and The National, fetch the existing Source URL with one transparent static HTTP GET, no redirects/retries, at most 100 candidate anchors and 20 accepted recent direct articles per publisher. Native feeds and other publishers receive no supplement.

Only defensibly dated articles in the existing seven-day window qualify. Missing/unzoned/future/stale dates are skipped. National literal URL-path dates retain an explicit day-only limitation. Unknown dates are never invented.

Before Luna, match by publisher and exact canonical URL, or full normalized headline with dates within 24 hours. Only one-to-one matches merge; ambiguity stays separate. A matched Google wrapper receives a direct canonical URL while retaining its original feed URL for processed exclusion and both origins for provenance. Feed-only articles remain in place. The existing classification/enrichment/selection path handles the merged pool.

Audits and terminal counters distinguish rss/google_news_rss/direct_site/discovery_fallback and include per-source counts, replacements, ambiguity/duplicates, Luna and enrichment attempts, raw retriever outcomes and selections. The detailed implementation and full field definitions are in docs/hybrid_discovery.md.

## Limits

The single GET rule skips redirects: National contributed no guaranteed fresh-fetch coverage, because its benchmark Source URL redirected to /uae/. The saved National HTML replay is parser validation only. Existing httpx/lxml implement the transparent static strategy; Scrapling/curl transport parity has not been tested live. No dependencies were added and there is no Scrapling body fallback.

## Cached HTML parser replay (no network)

| Publisher | Accepted recent | Candidate anchors | Prior listing redirects |
|---|---:|---:|---:|
| Arab News | 20 | 54 | 0 |
| Khaleej Times | 12 | 45 | 0 |
| Saudi Gazette | 18 | 48 | 0 |
| The National | 20 | 21 | 1 |

Counts use the frozen benchmark HTML and its recorded fetch time. They are not a new collection or an estimate of Luna relevance/selection gains.

## Verification

- Full pytest: **672 passed in 6.60s**, including **36 new offline cases**.
- git diff --check: **passed**; added files also checked for trailing whitespace and final newlines.
- Prompts, classifier/enricher clients, Luna allocation, event/final selection, existing ArticleRetriever, dependencies and Notion schema verified unchanged against HEAD. .env and ingestion state hashes match the pre-existing benchmark manifest.

## Files changed

- .env.example
- README.md
- docs/hybrid_discovery.md
- src/research_automation/config.py
- src/research_automation/models/article.py
- src/research_automation/sources/rss.py
- src/research_automation/pipeline/discovery.py
- src/research_automation/pipeline/direct_site_discovery.py
- src/research_automation/pipeline/ingestion.py
- src/research_automation/pipeline/candidate_audit.py
- tests/test_config.py
- tests/test_hybrid_discovery.py

Additional local artifacts: this report, verification.json and offline_listing_replay.json in the requested evaluation workspace. Earlier discovery benchmark code/artifacts retained unchanged.

## Next Luna/Sol shadow command (not executed)

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:DIRECT_SITE_DISCOVERY_ENABLED = "true"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-sol"
.\.venv\Scripts\python.exe -X utf8 scripts\run_daily_ingestion_local.py --dry-run --all-sources --limit 12
```

This user-invoked dry run makes paid classifier/enrichment calls, but no Notion or ingestion-state writes. Disable afterwards with $env:DIRECT_SITE_DISCOVERY_ENABLED = "false". Classifier batch 100, enrichment 32/48/8, thresholds, scoring, caps, regional targets and provider budgets are not overridden.

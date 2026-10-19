# Research Automation

Local Python automation for a Notion-based research workflow. The project validates and schedules a Notion Source Registry, builds a bounded article candidate pool, ranks every shortlisted candidate before writing, and generates weekly newsletter and social draft content from human-approved items only.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
```

Required `.env` values include the five Notion database IDs, Notion and OpenAI credentials, and the runtime/selection settings documented in `.env.example`. Never commit `.env` or real secrets.

## Scripts

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python scripts\test_notion_connection.py
.\.venv\Scripts\python scripts\inspect_notion_database.py source_registry
.\.venv\Scripts\python scripts\run_weekly_setup_local.py
.\.venv\Scripts\python scripts\run_daily_ingestion_local.py --dry-run
.\.venv\Scripts\python scripts\run_daily_ingestion_local.py --dry-run --all-sources
.\.venv\Scripts\python scripts\run_daily_ingestion_local.py --limit 5
.\.venv\Scripts\python scripts\run_weekly_drafts_local.py
```

## Workflow

1. The revised Source Registry schema is validated before ingestion.
2. Due `Publisher` rows are selected from `Check Frequency`; `Discovery Provider` rows are demand-triggered only.
3. Due feeds are fetched concurrently with bounded HTTP retries and per-source health outcomes.
4. The default `ARTICLE_SELECTION_MODE=deterministic` follows the legacy steps below. Opt-in `luna` uses objective cleanup, batched GPT-6 Luna metadata classification, a merged bounded enrichment pool and regional coverage with quality-based overflow. See [controlled Luna selection and dry run](docs/luna_selection.md).
   In deterministic mode, URLs are normalized, deduplicated, assigned to exact quota regions, and filtered for freshness, topic, and geography.
5. Up to six candidates per deficient region are shortlisted initially and at most eight are attempted per execution. Direct mission signals precede contextual matches; within each tier, mission specificity, publisher quality and concrete developments precede recency and snippet length, while retaining publisher diversity. Expansion reserves up to two available attempts for metadata-eligible discovery results and returns unused capacity to RSS.
6. The final queue score is 70% LLM relevance, 20% editorial significance and 10% publisher `Editorial Quality`. Registered publishers require relevance 4; unregistered publishers require 5.
7. Selection enforces weekly targets of Global 3, UAE 4, KSA 3, and Egypt 2, with a hard two-per-publisher weekly cap and same-event suppression.
8. Only final winners are written as complete Article Queue pages. The weekly target and per-execution ceiling are both 12 pages.
9. Dry runs load current weekly state and perform no Notion or ingestion-state writes. Both live runs and dry runs write metadata-only candidate diagnostics outside ingestion state.
10. Human editors approve stories in Notion, after which the unchanged weekly draft flow uses approved articles.

`--no-enrich` is diagnostic-only and requires `--dry-run`; it can never create live queue pages.

An optional four-publisher direct-listing supplement is available for shadow dry
runs only. `DIRECT_SITE_DISCOVERY_ENABLED=false` remains the default; see
[hybrid discovery bounds, provenance and Luna/Sol command](docs/hybrid_discovery.md).

Google News URL resolution is separately opt-in and default-off. It runs only
immediately before detailed-enrichment evidence retrieval; see
[resolver bounds, fallback, audit metrics and shadow command](docs/google_news_resolution.md).

Candidate audits are saved as timestamped Markdown and JSON files in ignored `.preview/ingestion_audits/` (beside the configured local-state directory). The console prints the Markdown path. Each phase observation records assignment and ordering reasons, origin and publisher registration, signals, shortlist/attempt status and available scores. Audits distinguish unique original-URL identities from reconsiderations across phases and canonical aliases; stage counts are explicitly per phase. They contain no article bodies, API credentials, snippets or raw provider errors. Audit output is diagnostic only and is never used for deduplication or scheduling. Audit write failures are logged without stopping ingestion.

Pre-LLM duplicates are skipped and backfilled without consuming the eight-attempt ceiling; failed LLM calls still count. Audits now distinguish decision stages and include existing retrieval status and significance rationale. The [routing policy](docs/candidate_selection_routing.md) documents project location versus company nationality, other-MENA coverage in the existing Global quota, discovery query hints, and narrow topic/source exclusions.

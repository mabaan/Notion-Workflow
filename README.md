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
4. URLs are normalized, deduplicated, assigned to exact quota regions, and filtered for freshness, topic, and geography.
5. Up to six candidates per deficient region are shortlisted initially and at most eight are enriched per execution.
6. The final queue score is 90% LLM relevance and 10% publisher `Editorial Quality`.
7. Selection enforces weekly targets of Global 3, UAE 4, KSA 3, and Egypt 2, with a hard two-per-publisher weekly cap and same-event suppression.
8. Only final winners are written as complete Article Queue pages. The weekly target and per-execution ceiling are both 12 pages.
9. Dry runs load current weekly state and perform no Notion or local-state writes.
10. Human editors approve stories in Notion, after which the unchanged weekly draft flow uses approved articles.

`--no-enrich` is diagnostic-only and requires `--dry-run`; it can never create live queue pages.

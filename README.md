# SOMA MATER Research Automation

Python automation for collecting and curating Food & Water Security and Net Zero
Transition news, especially in MENA. Qualified articles enter a Notion Article
Queue for human approval before newsletter and social drafts are generated.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
```

Fill in the Notion integration token, five database IDs and OpenAI credentials.
Use the keys in [.env.example](.env.example) and see [Notion setup](docs/notion_setup.md).
Keep `.env` and `.local_state/` private and local.

## Run ingestion

The current Luna/Sol workflow uses these explicit session settings. The shipped
selection default remains `deterministic` for rollback.

```powershell
$env:ARTICLE_SELECTION_MODE = "luna"
$env:GOOGLE_NEWS_URL_RESOLUTION_ENABLED = "true"
$env:DIRECT_SITE_DISCOVERY_ENABLED = "false"
$env:CLASSIFICATION_MODEL = "gpt-6-luna"
$env:LLM_MODEL = "gpt-6-sol"

# Review the same selection path without Notion or ingestion-state writes.
.\.venv\Scripts\python.exe -X utf8 scripts\run_daily_ingestion_local.py --dry-run --all-sources --limit 12

# Save qualified winners to Article Queue for human review.
.\.venv\Scripts\python.exe -X utf8 scripts\run_daily_ingestion_local.py --all-sources --limit 12
```

Dry runs can make paid model/discovery requests. `--all-sources` bypasses publisher
scheduling; existing queue counts, processed history and weekly caps still apply.
`--limit` is a maximum. A full week skips collection and model work. There is no
CLI switch to ignore existing queue/history. `--dry-run --no-enrich` provides
metadata diagnostics without classification or enrichment model calls.

## Selection

1. Load weekly queue state and remaining capacity; fetch due publisher RSS feeds.
2. In Luna mode, apply objective validity, freshness, URL deduplication and
   processed/self-published exclusions, then classify all eligible metadata in
   batches of 100. No keyword editorial gate runs in this path.
3. Merge classifications and allocate detailed enrichment: 32 initial attempts,
   backfill in batches of 8, and at most 48 attempts across RSS and discovery.
   Resolve Google News URLs only at allocated retrieval opportunities when enabled.
4. Select strict winners first: relevance at least 4 for registered publishers,
   5 for unregistered publishers. Already-enriched registered stories with
   relevance and significance at least 3 can fill remaining capacity via fallback.
5. Rank by 70% final relevance, 20% editorial significance and 10% publisher quality.
   Enforce event deduplication, two articles per publisher per week, regional
   coverage preferences and the total weekly capacity of 12 by default.
6. Write complete winners to Article Queue and record successful URLs locally.
   Weekly drafting subsequently uses only human-approved articles.

See [architecture](docs/architecture.md), [Luna selection](docs/luna_selection.md),
[classifier](docs/article_classifier.md), [Google News resolution](docs/google_news_resolution.md)
and [optional direct-site shadow discovery](docs/hybrid_discovery.md).
The [deterministic routing policy](docs/candidate_selection_routing.md) documents
the rollback path.

## Other commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\test_notion_connection.py
.\.venv\Scripts\python.exe scripts\inspect_notion_database.py source_registry
.\.venv\Scripts\python.exe scripts\run_weekly_setup_local.py
.\.venv\Scripts\python.exe scripts\run_weekly_drafts_local.py
```

Generated audits, run logs, draft previews and evaluation captures belong in
ignored `.preview/`. Tests and their small reference fixtures remain tracked.
See [evaluation tools and artifact handling](docs/evaluation.md) for offline
benchmarks and historical inputs.

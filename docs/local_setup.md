# Local Setup

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
```

## Configure `.env`

Fill in the Notion integration token, the five database IDs, and the OpenAI API key. Keep `.env` gitignored.

The weekly targets total 12 (`Global=3`, `UAE=4`, `KSA=3`, `Egypt=2`), matching the `MAX_ARTICLES_PER_RUN=12` per-execution safety ceiling. A later execution loads current weekly state and can add only the remaining qualified positions.

```env
MAX_ARTICLES_PER_RUN=12
MAX_ARTICLES_PER_PUBLISHER_PER_WEEK=2
ARTICLE_QUEUE_WEEKLY_TARGET_GLOBAL=3
ARTICLE_QUEUE_WEEKLY_TARGET_UAE=4
ARTICLE_QUEUE_WEEKLY_TARGET_KSA=3
ARTICLE_QUEUE_WEEKLY_TARGET_EGYPT=2
ARTICLE_FRESHNESS_DAYS=7
ARTICLE_SHORTLIST_INITIAL_PER_REGION=6
ARTICLE_SHORTLIST_MAX_PER_REGION=8
```

## Run the Local Workflow

```powershell
.\.venv\Scripts\python scripts\test_notion_connection.py
.\.venv\Scripts\python scripts\inspect_notion_database.py source_registry
.\.venv\Scripts\python scripts\run_weekly_setup_local.py
.\.venv\Scripts\python scripts\run_daily_ingestion_local.py --dry-run
.\.venv\Scripts\python scripts\run_daily_ingestion_local.py --dry-run --all-sources
.\.venv\Scripts\python scripts\run_daily_ingestion_local.py --limit 5
.\.venv\Scripts\python scripts\run_weekly_drafts_local.py
```

The dedupe store is written to `.local_state/seen_articles.json` only after a Notion Article Queue page is created successfully.

Run `--dry-run` before live ingestion. It finds the current Dataset Meeting when present, loads existing weekly quotas and publisher counts, evaluates the same candidate path as live mode, and makes no Notion or local-state writes. `--all-sources` bypasses publisher scheduling for a manual health check. `--no-enrich` is permitted only together with `--dry-run`.

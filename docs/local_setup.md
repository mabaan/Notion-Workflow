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

## Run the Local Workflow

```powershell
.\.venv\Scripts\python scripts/test_notion_connection.py
.\.venv\Scripts\python scripts/inspect_notion_database.py source_registry
.\.venv\Scripts\python scripts/run_weekly_setup_local.py
.\.venv\Scripts\python scripts/run_daily_ingestion_local.py --dry-run
.\.venv\Scripts\python scripts/run_daily_ingestion_local.py --limit 5
.\.venv\Scripts\python scripts/run_weekly_drafts_local.py
```

The dedupe store is written to `.local_state/seen_articles.json` by default.

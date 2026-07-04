# Research Automation

Local Python automation for a Notion-based research workflow. The project reads active sources from a Notion Source Registry, fetches articles from feeds, deduplicates them locally, enriches them with OpenAI, creates Article Queue pages, and generates weekly newsletter and social draft content from human-approved items only.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
```

Required `.env` values:

- `NOTION_TOKEN`
- `NOTION_SOURCE_REGISTRY_DATABASE_ID`
- `NOTION_ARTICLE_QUEUE_DATABASE_ID`
- `NOTION_DATASET_MEETINGS_DATABASE_ID`
- `NOTION_NEWSLETTERS_DATABASE_ID`
- `NOTION_SOCIAL_MEDIA_DATABASE_ID`
- `LLM_PROVIDER`
- `LLM_MODEL`
- `OPENAI_API_KEY`
- `LOCAL_STATE_PATH`
- `LOG_LEVEL`
- `MAX_ARTICLES_PER_RUN`

Never commit `.env` or real secrets.

## Scripts

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python scripts/test_notion_connection.py
.\.venv\Scripts\python scripts/inspect_notion_database.py source_registry
.\.venv\Scripts\python scripts/run_weekly_setup_local.py
.\.venv\Scripts\python scripts/run_daily_ingestion_local.py --dry-run
.\.venv\Scripts\python scripts/run_daily_ingestion_local.py --limit 5
.\.venv\Scripts\python scripts/run_weekly_drafts_local.py
```

## Workflow

1. Active sources are read from the Source Registry database in Notion.
2. Feed-based sources are fetched locally with `feedparser`.
3. URLs are cleaned and deduplicated against `.local_state/seen_articles.json`.
4. New Article Queue pages are created in Notion and linked to the current week’s Dataset Meeting.
5. OpenAI enrichment fills summary, score, topic, region, and draft-angle fields.
6. Human editors approve stories in Notion.
7. Weekly setup creates or reuses the current Dataset Meeting, Newsletter, and Social Media pages.
8. Weekly draft generation uses only approved articles and updates automation-managed draft sections on the Newsletter and Social Media pages.

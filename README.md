# Research Automation

Python scaffold for collecting research articles, enriching them, and generating weekly draft content for Notion-backed workflows.

## Project Layout

- `src/research_automation/handlers`: Lambda-style entry points.
- `src/research_automation/sources`: Article source adapters.
- `src/research_automation/pipeline`: Collection, cleaning, deduplication, enrichment, and drafting steps.
- `src/research_automation/clients`: External service clients.
- `src/research_automation/prompts`: Prompt templates.
- `scripts`: Local utility runners.
- `docs`: Architecture, setup, deployment, and handover notes.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
```

## Useful Commands

```powershell
pytest
python scripts/run_ingestion_local.py
python scripts/run_weekly_draft_local.py
```


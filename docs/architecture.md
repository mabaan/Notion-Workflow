# Architecture

The local workflow is organized around a small set of modules:

1. `pipeline/source_registry.py` reads active sources from Notion.
2. `sources/rss.py` and `pipeline/collect.py` fetch feed entries.
3. `utils/urls.py` and `utils/hashing.py` normalize and hash article candidates.
4. `pipeline/deduplicate.py` stores seen article hashes in local JSON.
5. `pipeline/notion_write.py` and `pipeline/weekly_pages.py` manage Notion pages and relations.
6. `clients/llm_client.py` handles OpenAI enrichment and draft generation.

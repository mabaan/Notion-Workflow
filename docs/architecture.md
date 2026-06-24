# Architecture

The project is organized around a small ingestion and drafting pipeline:

1. Source adapters collect article candidates.
2. Pipeline steps clean, deduplicate, and enrich article records.
3. Draft generation turns selected articles into newsletter or social content.
4. Client modules isolate Notion, LLM, DynamoDB, and S3 integrations.


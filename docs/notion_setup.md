# Notion Setup

The local MVP expects five existing Notion databases:

- Source Registry
- Article Queue
- Dataset Meetings
- Newsletters
- Social Media Content

Store their database IDs in `.env` using the keys from `.env.example`.

## Live Schema Notes

The implementation targets the current live workspace exactly, including these quirks:

- `Article Queue` title property is `TItle`
- `Article Queue` score property is `Relevance  Score`
- `Source Registry` `Last Checked` is a `rich_text` property, not a date
- `Dataset Meetings`, `Newsletters`, and `Social Media Content` use `status` properties

Use `python scripts/inspect_notion_database.py <database>` any time you want to confirm the live schema.

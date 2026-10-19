# Notion Setup

The local workflow expects five existing Notion databases:

- Source Registry
- Article Queue
- Dataset Meetings
- Newsletters
- Social Media Content

Store their database IDs in `.env` using the keys from `.env.example`.

## Source Registry

Ingestion validates these properties before contacting any source:

| Property | Type |
| --- | --- |
| Source Name | Title |
| Source Type | Select |
| Active | Checkbox |
| Editorial Quality | Number |
| Acquisition Priority | Select |
| Credibility | Select |
| Check Frequency | Select |
| Collection Method | Select |
| Feed URL | URL |
| Source URL | URL |
| Region | Multi-select |
| Topic Focus | Multi-select |
| Last Attempt | Date |
| Last Success | Date |
| Last Outcome | Select |
| Last Error | Rich text |
| Articles | Relation |

`Source Type` must be `Publisher` or `Discovery Provider`. Publisher `Check Frequency` must be `Daily`, `Weekly`, or `On Demand`. Publisher Editorial Quality is a number from 1 through 10; an unrated publisher is allowed with a warning. Discovery providers can omit a Feed URL.

The code does not mutate this schema. Missing or mistyped properties stop ingestion with a complete error list.

## Live Schema Notes

The implementation retains these Article Queue and weekly-database names:

- `Article Queue` title property is `TItle`
- `Article Queue` relevance property is `Relevance  Score`
- `Dataset Meetings`, `Newsletters`, and `Social Media Content` use `status` properties

The Source Registry uses `Acquisition Priority`, `Last Attempt`, `Last Success`, `Last Outcome`, and `Last Error`; obsolete `Priority` and `Last Checked` fields are not read.

`Queue Score` (Number) and `Selection Reason` (Rich text) are optional Article Queue properties. If absent, the run logs both values instead of requiring a schema mutation.

Use `python scripts/inspect_notion_database.py <database>` to confirm the live schema.

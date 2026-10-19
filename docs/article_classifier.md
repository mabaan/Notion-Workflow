# Metadata classifier

This reusable component now powers the opt-in `ARTICLE_SELECTION_MODE=luna` ingestion path. The default remains `deterministic` for rollback. See [controlled Luna selection](luna_selection.md) for allocation, discovery, coverage overflow, audit fields and the dry-run command.

`ArticleClassifier.classify()` accepts `ClassificationInput` records containing a caller-supplied stable ID, title, RSS snippet, publisher, publication datetime and source-region hints. It sends only those fields. Titles and snippets are JSON data in the user message; trusted instructions and the editorial rubric stay in the system message. Publisher/discovery regions are explicitly labelled hints, never geographic proof. No article is fetched.

Each successful result contains the ID, relevance 1-5, assigned region, primary mission topic, Relevant/Borderline/Irrelevant decision and a justification of at most 240 characters. Allowed regions are Global, UAE, KSA, Egypt and Out of Scope/Unclear. Topics are Food Security, Water Security, Net Zero Transition and Other/Unclear.

Results also require `story_type` (the compact shared primary-subject enum) and
`is_new_development` (JSON `true`, JSON `false`, or the string `"unclear"`). Both
fields are required in the strict JSON schema and checked locally, without
coercion. Clear background, general politics/conflict, humanitarian relief and
routine-event coverage is Irrelevant; a plausible but unresolved mission
development remains Borderline. Sector policy is distinct from general politics.
Material mission consequences of conflict use a mission type such as
`supply_disruption` when that consequence is the primary news. New systemic climate
measurements and transition-material investigations can qualify as Global without
a named MENA country. These metadata judgments never override the detailed
assessment; see [final editorial scope](luna_selection.md#current-editorial-scope).

The [prompt](../src/research_automation/prompts/article_classification.txt) prefers recall: potentially important articles with incomplete metadata stay Borderline. Mere keywords do not establish high relevance. Geography follows the event/project; other-MENA locations such as Iraq and Palestine use Global. Unclear geography alone does not establish irrelevance. This stage assigns mission fit, not editorial significance.

## Use and objective preparation

```python
from research_automation.clients.article_classifier import ArticleClassifier
from research_automation.pipeline.article_classification import prepare_classification_inputs

# settings, articles, now and processed_urls come from the explicit caller.
prepared = prepare_classification_inputs(
    articles,
    now=now,
    freshness_days=settings.article_freshness_days,
    excluded_urls=processed_urls,
    seen_url_hashes=processed_url_hashes,
)
classifier = ArticleClassifier(settings)
report = classifier.classify(prepared.inputs)
```

Preparation is optional when the caller already has valid, eligible metadata. It performs only URL/title/date validity, the existing freshness cutoff, exact/canonical URL deduplication, supplied processed-URL/hash exclusions and self-published-domain exclusion. It never calls the keyword or regional editorial gates. IDs are canonical URL hashes. Every exclusion is returned in `prepared.excluded`; source articles and local state are not mutated. Only one copy of a canonical URL is classified, with later copies recorded as duplicates.

Callers can instead build `ClassificationInput` records directly with their own stable IDs. Invalid metadata or duplicate/empty IDs raise `ValueError` before any request. URL validity and freshness are then the caller's responsibility.

An explicitly unknown publication date can be represented by `None` and is sent as JSON `null`, for example when evaluating historical title-only records. The objective preparation adapter still excludes unknown publication dates; this does not relax ingestion freshness requirements.

## Configuration

These settings reuse `OPENAI_API_KEY`. Luna ingestion requires `CLASSIFICATION_MODEL=gpt-6-luna`; enrichment accepts `LLM_MODEL=gpt-6-luna` or `gpt-6-sol`. The independent component retains older verified profiles for historical experiments.

| Environment variable | Default | Meaning |
|---|---|---|
| `CLASSIFICATION_MODEL` | `gpt-6-luna` | Luna ingestion uses Luna; independent historical profiles also include mini/nano |
| `CLASSIFICATION_BATCH_SIZE` | `100` | Maximum articles in each initial request group |
| `CLASSIFICATION_MAX_REQUEST_BYTES` | `200000` | Preflight UTF-8 JSON request-size budget |
| `CLASSIFICATION_MAX_OUTPUT_TOKENS` | `32768` | Completion budget; also constrains estimated batch output |
| `CLASSIFICATION_MAX_ATTEMPTS` | `2` | Attempts including the first, bounded to 1-3 per sub-batch |
| `CLASSIFICATION_TIMEOUT_SECONDS` | `120` | Allows the measured approximately 73-second 100-article Luna requests |

Classifier settings are validated when the classifier is constructed. The installed SDK exposes `response_format` and `max_completion_tokens`. Official model documentation confirms Chat Completions, structured outputs and a 32,768-token output limit for [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) and [GPT-4.1 nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano). Both profiles use a 1,047,576-token context limit. [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) supports the same endpoint/structured output, with 1,050,000 context and 128,000 maximum output tokens; it uses medium reasoning to match the existing enrichment client. Sampling parameters are omitted. Unknown models are rejected until their endpoint, structured-output capability and limits are verified and added to `MODEL_LIMITS`. These profiles have been exercised in the limited evaluation below; availability and lifecycle must be checked for later deployments.

## Batching, validation and recovery

Inputs are sorted by ID for stable batch membership. All groups are processed, including the final partial group; outcomes return in the caller's original order. With ordinary fixture metadata, 250 articles produce requests of 100, 100 and 50.

Before requesting, groups are bisected until the serialized UTF-8 request fits its byte/context budget and estimated output fits the configured output budget. Output estimation reserves 256 tokens plus 256 and ID bytes per article. It is intentionally approximate; actual output truncation and API context/request-size errors immediately trigger smaller groups. Metadata is never silently truncated. An oversized singleton gets an explicit unresolved outcome.

The same fixed JSON Schema is sent to the provider and validated locally with a small standard-library validator for its exact subset (objects, arrays, strings, integers, booleans, anyOf, enums, bounds and required fields). It rejects coercible scores/novelty, extra/missing fields, invalid enums and duplicate JSON keys. Input-ID enums, exact result cardinality and a uniqueness check require exactly one row for each requested ID. Unknown, repeated or missing IDs invalidate the whole response, including apparently valid rows. No positional matching or partial acceptance is used.

Malformed responses and transient failures have bounded retries with short exponential delays. Exhausted malformed responses/timeouts are bisected to isolate failing inputs. Rate-limit and server failures stop that group after its bounded attempts and allow later groups to proceed. Permanent request/authentication/model errors stop further requests for that invocation. SDK retries are disabled so request accounting remains exact. For persistently malformed responses, a group of N inputs has at most `max_attempts * (2*N - 1)` API attempts; preflight-only splits do not consume requests.

There is exactly one `ClassificationOutcome` per submitted ID. Failed outcomes contain an error category and no fabricated editorial score. `report.eligible_ids` includes Relevant, Borderline **and unresolved failures**; only an explicit Irrelevant classification excludes an article. Callers must retain or retry unresolved IDs rather than silently dropping them. `failed_ids` makes operational failures visible separately from editorial decisions.

`report.requests` records input IDs, requested/returned models, attempt, status and provider-reported prompt/completion/total tokens, including malformed responses. `request_count`, `token_usage` and `requests_without_usage` summarize costs without pretending that unreported usage is known. A summary is logged without article bodies or raw API errors. Reports are returned in memory; this component writes no files or Notion pages.

## Validation and limits

Mock HTTP tests cover default/custom batches, all-input coverage, reversed response/input order, strict field/ID validation, retries, truncated output, context/byte limits, Unicode metadata, isolated failures, authentication/rate-limit failures, usage accounting, objective prechecks and untrusted-data prompt boundaries. They use the real SDK with `httpx.MockTransport`; no live classification or Notion calls are made.

Metadata can omit important facts, and prompt instructions cannot guarantee model judgment or immunity to adversarial text. Offline tests verify request and selection mechanics; historical experiments use provisional reference labels and saved metadata. Population recall/precision remain unestablished. Binary recovery can increase requests on malformed responses. Byte/output estimates are conservative heuristics with runtime size recovery. The current opt-in integration retains Borderline and unresolved operational failures for bounded detailed assessment; unassessed failures stay explicit in the audit.

## Offline benchmark

`tests/fixtures/article_classifier_benchmark.json` retains saved metadata,
provenance and provisional analyst labels. Missing descriptions stay empty;
missing-date supplements and user-described scenarios remain separate from dated
historical articles. Prior model outputs are not reference labels.

`scripts/evaluate_article_classifier.py` runs the deterministic baseline offline
by default. Other retained tools compare shared enrichment, batch consistency
and evidence retrieval. Historical captures are local artifacts rather than
source files; see [evaluation tools and artifact handling](evaluation.md) for
inputs, output locations and replay requirements.

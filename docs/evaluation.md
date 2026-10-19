# Evaluation tools and local artifacts

Reusable pipeline code, benchmark tools, tests and small fixtures are tracked.
Generated reports, request/response captures, source snapshots, downloaded
repositories, isolated experiment environments and manual run receipts belong
under ignored `.preview/`. Persistent URL/image state remains in `.local_state/`;
it is not a disposable preview artifact.

## Offline checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.evaluate_article_classifier --help
git diff --check
```

The test suite uses mocked inputs and HTTP responses. The optional installed
Scrapling test skips when its separate benchmark interpreter is absent; Scrapling
is not a production dependency. The main project's `.venv` is retained.

## Retained benchmark tools

| Script in `scripts/` | Purpose and inputs |
|---|---|
| `evaluate_article_classifier.py` | Deterministic/classifier comparison using the tracked metadata benchmark; baseline runs offline |
| `evaluate_enriched_selection.py` | Compare both screens with the same captured enrichment; requires a classifier evaluation directory |
| `evaluate_luna_followup.py` | Historical 100/50 batch consistency and enrichment-panel experiment; requires a frozen 100-record snapshot and prior captures |
| `evaluate_google_news_resolution.py` | Wrapper-resolution benchmark using an existing audit, source snapshot and frozen dataset |
| `evaluate_direct_site_discovery.py` | Read-only listing/feed/retrieval comparison with a separate optional Scrapling interpreter |
| `evaluate_scrapling_retrieval.py` | Existing retriever versus optional isolated extraction/rendering methods, using a frozen dataset |
| `prepare_article_classifier_benchmark.py` | Reconstruct the original convenience fixture from saved metadata; changes reference inputs, so use deliberately |

These scripts are outside production ingestion. Running tests or `--help` does
not launch a live experiment. Some historical tools retain dated default input
paths and fixed experiment/model/token limits; they require their saved captures
before replay. Read each script's help and input requirements before using it.
Live options can perform network/model work and are separate from offline tests.
Recorded pricing assumptions are historical, not a current billing quote.

## Capture handling

Saved captures are optional replay inputs, not runtime dependencies. Historical
tools may require their original `.preview` snapshots; restore previously tracked
inputs from Git history when needed. Missing captures do not authorize new
collection or paid experiments. Use a fresh output directory for a new evaluation.

Do not add generated captures to source control. Promote only compact, necessary
regression inputs to `tests/fixtures/`, preserving provenance, missing evidence
and reference-label limitations. Disposable local captures can be deleted.

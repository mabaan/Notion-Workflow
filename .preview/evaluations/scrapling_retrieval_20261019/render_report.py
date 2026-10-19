"""Produce retrieval metrics/report from captured records only; no network."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
from importlib.metadata import version
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts import evaluate_scrapling_retrieval as bench

OUT = Path(__file__).resolve().parent
dataset = json.loads((OUT / "dataset_complete.json").read_text(encoding="utf-8"))
rows = []
for directory in ("run", "publisher_url_pairs"):
    rows.extend(json.loads(line) for line in (OUT / directory / "results.jsonl").read_text(encoding="utf-8").splitlines())
metrics = bench.summarize(rows)
bench.write(OUT / "metrics.json", metrics)
bench.write(OUT / "results.json", rows)
all_methods = {row["method"]: row for row in metrics if row["publisher"] == "ALL"}
before = json.loads((OUT / "protected_before.json").read_text(encoding="utf-8"))
changed = [name for name,digest in before.items() if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest]
assert not changed, changed
bench.write(OUT / "integrity.json", dict(protected_existing_files=len(before), changed_existing_files=changed,
                                       production_state_unchanged=True, paid_llm_requests=0, notion_writes=0))
python = OUT / ".venv/Scripts/python.exe"
lock = subprocess.run([str(python), "-m", "pip", "freeze", "--local"], capture_output=True, text=True, check=True).stdout
(OUT / "requirements-benchmark.txt").write_text(lock, encoding="utf-8")
check = subprocess.run([str(python), "-m", "pip", "check"], capture_output=True, text=True)
assert check.returncode == 0, check.stdout + check.stderr
(OUT / "pip_check.txt").write_text(check.stdout + check.stderr, encoding="utf-8")
bench.write(OUT / "environment.json", dict(
    baseline_python=sys.executable, baseline_readability=version("readability-lxml"),
    baseline_cssselect=version("cssselect"), baseline_httpx=version("httpx"),
    scrapling_python=str(python), isolated_system_packages=False,
    scrapling_version="0.5", reference_commit="fd531313a499092d8471bf24a0e08dc5771f2b40",
    dependency_conflict="readability-lxml 0.9 requires cssselect>=1.3,<1.4; Scrapling 0.5 requires cssselect>=1.5.0",
    browser_binaries_installed=False, browser_fetches=0,
))

fields = ["case_id", "title", "publisher", "url", "stratum", "selected", "original_retrieval_status", "method", "attempted", "status", "raw_status", "http_status", "characters", "title_match", "page_title", "canonical_url", "canonical_resolution_success", "latency_seconds", "worker_wall_seconds", "fallback_used", "reason"]
with (OUT / "article_results.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        for method,result in row["results"].items():
            writer.writerow(dict(row, case_id=row.get("case_id",row["article_id"]), **result))

def rate(count, total):
    return f"{count}/{total} ({100*count/total:.1f}%)" if total else "not measured"

lines = ["# SOMA MATER — Scrapling retrieval benchmark", "", "## Recommendation: NO-GO for production integration", "",
"Scrapling static recovered **zero additional article bodies**. The current bottleneck is primarily unresolved Google News input URLs, not a demonstrated weakness in public publisher-page extraction. On the seven direct publisher URLs, the baseline extracted six bodies; one Reuters request was blocked and was not escalated. Scrapling extracted the same six permitted pages. No public page met the rendering criteria, so rendered effectiveness is unmeasured.", "",
"## Dataset and provenance", "",
"- **42 distinct URLs for 40 distinct articles**, across 11 publisher labels: a primary 40-URL snapshot plus two separately reported direct-URL diagnostics for the same stories.",
"- Primary snapshot: 3 retrievable final-selected records, 17 enriched weak-evidence records, 3 successful-retrieval controls, and 17 classified metadata supplements from the latest audit. Three other selected records are retained as unavailable-URL entries, outside retrieval denominators.",
"- Source: [latest audit](../../ingestion_audits/20261019T131713503320Z_0b40c7fc.json). It records 48 enrichments: 45 insufficient_content and 3 extracted. All six final selections had insufficient_content.",
"- Saved metadata/URLs came from the existing Luna evaluation snapshot. Exact-ID and normalized-title match provenance is recorded per row. Missing descriptions remain empty. Five known publisher URLs were recovered by exact-headline lookup; no newly discovered stories were added.",
"- **35 Google News wrapper URLs and 7 direct publisher URLs.** Two matched-story direct URLs (The National and Arab News) were frozen as a diagnostic before measuring those URL variants. Improvements from changing a wrapper to a publisher URL are not credited to Scrapling.",
"- [Complete reproducible dataset](dataset_complete.json), [primary frozen snapshot](dataset.json), [publisher-URL diagnostic](publisher_url_pairs.json), [126 method-level rows](article_results.csv), [captured results](results.json), and [machine metrics](metrics.json).", "",
"### Selected-article coverage gap", "",
"Only **3 of the 6 selected articles have recoverable original-publisher URLs or saved input URLs**. The Nature conservation article succeeds with both tools; the Reuters Amazon story remains an unresolved Google News input; the direct Reuters food-inflation URL refuses access. The following original URLs were not retained in the supplied audit or available saved metadata:", ""]
for item in dataset["unavailable_selected"]:
    lines.append("- " + item["title"])
lines += ["", "All six selected records are represented in the manifest, but these three could not be fetched without guessing or substituting another publisher. They are **not counted as retrieval failures or successes**. Related coverage at other outlets was not used as a substitute. Publisher access refusals observed during lookup for agbi.com and zawya.com are preserved; the benchmark does not request those origins.", "",
"## Method results", "", "| Method | URLs evaluated | URLs attempted | Valid article bodies | Insufficient | Fetch failed | Blocked | Wrong-page extraction | Canonical success | Median body chars (successful) | Median latency (attempted) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
for name in bench.METHODS:
    row = all_methods[name]
    statuses = row["statuses"]
    latency = str(row["median_latency"]) + " s" if row["median_latency"] is not None else "not measured"
    lines.append(f"| {name} | {row['urls']} | {row['attempted']} | {row['successful']} | {statuses.get('insufficient_content',0)} | {statuses.get('fetch_failed',0)} | {statuses.get('blocked',0)} | {statuses.get('wrong_page',0)} | {row['canonical_resolved']} | {row['median_characters']} | {latency} |")
lines += ["", f"Baseline success: **{rate(all_methods['baseline']['successful'],42)}**. Static success over the same URL set: **{rate(all_methods['scrapling_static']['successful'],42)}**; among static calls actually permitted/attempted: **{rate(all_methods['scrapling_static']['successful'],41)}**. Static incremental recovery: **0**. Renderer attempts: **0**, incremental recovery **0**, effectiveness **not measured**.", "",
"The static blocked count includes one skipped URL after the baseline's Reuters HTTP refusal; it is not a second HTTP attempt. The median extracted-character count across all attempted URLs is zero for both fetchers, because the 35 wrapper inputs yield no article text. Fetch/parse latency excludes Python worker startup; worker_wall_seconds records the total per-URL worker cost. Timing is a single sequential observation, not a controlled performance estimate.", "",
"## Publisher breakdown", "", "| Publisher | URL cases | Google wrappers | Baseline bodies | Static bodies | Baseline insufficient / blocked | Static insufficient / blocked | Baseline median seconds | Static median seconds |", "|---|---:|---:|---:|---:|---|---|---:|---:|"]
publishers = sorted({r["publisher"] for r in rows})
for publisher in publishers:
    first = next(r for r in metrics if r["publisher"]==publisher and r["method"]=="baseline")
    second = next(r for r in metrics if r["publisher"]==publisher and r["method"]=="scrapling_static")
    subset = [r for r in rows if r["publisher"]==publisher]
    lines.append(f"| {publisher} | {len(subset)} | {sum(bench.is_google_news_url(r['url']) for r in subset)} | {first['successful']} | {second['successful']} | {first['statuses'].get('insufficient_content',0)} / {first['statuses'].get('blocked',0)} | {second['statuses'].get('insufficient_content',0)} / {second['statuses'].get('blocked',0)} | {first['median_latency']} | {second['median_latency']} |")
lines += ["", "Every publisher's method-level attempts, status counts, canonical results, character medians and latency medians are retained in metrics.json. The table's publisher labels are the original audit labels; the rows do not imply that a wrapper input reached that publisher.", "",
"- Existing retrieval works on the tested direct pages from Dubai Eye, Guardian, Farrelly Mitchell, Nature, The National and Arab News (one direct page each). This is limited coverage, not a publisher-wide reliability estimate.",
"- Static material improvement: **none observed**. Rendered material improvement: **not tested; no eligible page**.",
"- Neither resolves the 35 Google wrapper inputs. Reuters has a separate direct-origin refusal. AGBI, ZAWYA, Gulf News and Saudi Press Agency only have wrapper inputs here; their article-body extraction reliability is not established by this sample.", "",
"## Quality checks and safeguards", "",
"Success requires at least 300 characters, a plausible article URL/page structure, expected-title overlap (>=0.45), subject overlap with extracted text, and article prose. Canonical metadata is accepted only for the same publisher host. Home/category/search canonicals, mismatched/error pages, Google wrappers, explicit paywalls/login requirements and challenge headings cannot count as bodies. Tests cover long navigation/cookie/error text and wrong-page cases. These heuristics assess plausibility, not factual accuracy or guaranteed completeness.", "",
"A Farrelly Mitchell control initially returned a 319-character heading/hero-sized extract. The generic selector validation was tightened to require 300 characters of paragraph prose inside a container; no publisher-specific selector was added. A single static quality recheck then extracted a bounded 12,000-character body. See run/body_quality_check.json. No accepted wrong-page extraction remained; 35 wrapper pages are classified insufficient, with the unresolved-wrapper reason recorded.", "",
"Bounds: 2,000,000 response bytes; 12,000 text characters; approximately 300-character minimum; HTTP connect/read bounds matching the baseline; 20-second static request timeout; at most five redirects; 35-second hard worker lifetime. Rendered design caps eight URL attempts, 40 GET requests/page, 2MB per response and 10MB aggregate, blocks large media, and stops on refusals. No renderer or browser binary was needed in this run.", "",
"Baseline calls the existing ArticleRetriever unchanged with a capturing client. Baseline refusal prevents trying another fetcher. Static uses Fetcher.get with impersonate=None, stealthy_headers=False, the same transparent research User-Agent, one attempt, manual bounded redirects and a bounded content_callback. Inherited proxy variables are removed in workers. No proxies, authentication, login state, CAPTCHA automation or anti-bot evasion are used. Text bodies are processed in memory; only metadata, hashes, counts and quality cues are retained.", "",
"The first static adapter used an unsupported curl_options request keyword. Those 39 local setup errors occurred before static HTTP requests and are excluded from publisher outcomes. The corrected pass reuses all baseline results and makes the first actual static request for each permitted case. An offline test now exercises the installed Fetcher-to-curl Session argument forwarding. setup_results.jsonl and setup_correction.json preserve that history.", "",
"## Current Scrapling API and dependencies", "",
"Reviewed current upstream commit fd531313a499092d8471bf24a0e08dc5771f2b40 and installed PyPI **Scrapling 0.5** (17 October 2026 release). [Static API](https://github.com/D4Vinci/Scrapling/blob/v0.5/docs/fetching/static.md), [v0.5 migration](https://github.com/D4Vinci/Scrapling/blob/v0.5/docs/migrating-to-v0.5.md), and [package requirements](https://github.com/D4Vinci/Scrapling/blob/v0.5/pyproject.toml).", "",
"- Public static HTML: Fetcher.get + Selector CSS/XPath/get_all_text; canonical links are ordinary HTML metadata. Scrapling supplies parsing primitives, not proof of article-body completeness.",
"- Markdown: Response.markdown(main_content_only=True) filters to body, not a guaranteed article region. It additionally requires markdownify; plain text was sufficient, so rag/ai/shell/full extras were not installed.",
"- JavaScript: DynamicFetcher was removed in v0.5. The remaining Scrapling browser API is stealth-based, so the benchmark's optional rendered adapter uses **ordinary Playwright + Scrapling Selector**, not StealthyFetcher/Patchright browser execution. No eligible case needed it, and Playwright/browser binaries were not installed. This path's live effectiveness is unestablished.",
"- Isolated environment: .preview/evaluations/scrapling_retrieval_20261019/.venv, with system packages disabled. Explicit packages: scrapling==0.5, curl_cffi==0.16.3, patchright==1.64.1, browserforge==1.2.4, httpx==0.28.1. Patchright/browserforge are required by the static API's imports in this release; their stealth/browser functions were not used. Exact transitive versions: requirements-benchmark.txt. pip check passes.",
"- **Production compatibility conflict:** installed readability-lxml 0.9 requires cssselect>=1.3,<1.4, while Scrapling 0.5 requires cssselect>=1.5. They cannot be cleanly installed together as currently declared. Separate interpreters keep the actual baseline dependencies unchanged. No project dependency or production environment was modified.", "",
"## Article fallback versus discovery", "",
"**A. Article-body fallback:** NO-GO now. There is no measured recovery benefit, the unresolved input URL dominates, and direct integration has a dependency conflict. First retain original/resolved article URLs in audit exports and validate a larger direct-publisher-URL sample. Prefer RSS links/full content and the existing retriever where available. Do not add the proposed static/rendered fallback chain on these results.", "",
"**B. Publisher listing-page discovery:** not implemented or benchmarked. CSS/XPath parsing could technically support a small source-specific public listing fallback when RSS is genuinely absent/stale/weak, but it does not establish freshness, correct story URLs, complete discovery or access permission. A separate source-specific evaluation would be needed. Keep RSS first; there is no evidence here to replace discovery with crawling.", "",
"## Verification and reproducibility", "",
"Changed repository code: scripts/evaluate_scrapling_retrieval.py and tests/test_scrapling_retrieval.py only. Supporting dataset preparation, captured runs, setup diagnostics and reports stay under this evaluation directory. Existing production source/config/prompts/schema/state hashes match the initial manifest (integrity.json). No Notion, Luna/Sol, paid LLM API, RSS collection, Brave/NewsAPI or production-ingestion calls were made.", "",
"Verification: **21 benchmark tests passed; full pytest: 602 passed in 6.29s; git diff --check passed (exit 0)**. New-file whitespace checks also passed. The existing test_evidence.py CRLF advisory predates this task. Results are recorded in verification.json. Benchmark tests make no external requests; the installed Scrapling parser/Fetcher API is exercised with a fake HTTP Session. Ordinary rendering has unit-tested eligibility gates but no live test in this sample.", "",
"Recreate the isolated environment without editing project dependencies:", "", "```powershell",
".\\.venv\\Scripts\\python.exe -m venv .preview/evaluations/scrapling_retrieval_20261019/.venv",
".\\.preview\\evaluations\\scrapling_retrieval_20261019\\.venv\\Scripts\\python.exe -m pip install -r .preview/evaluations/scrapling_retrieval_20261019/requirements-benchmark.txt",
"```", "", "Replay the primary 40-URL metrics offline:", "", "```powershell",
".\\.venv\\Scripts\\python.exe -m scripts.evaluate_scrapling_retrieval",
"```", "", "Regenerate the combined 42-URL report offline:", "", "```powershell",
".\\.venv\\Scripts\\python.exe -X utf8 .preview/evaluations/scrapling_retrieval_20261019/render_report.py",
"```", "", "Explicit future fetch-only repeat (not executed by this report; use a fresh output directory):", "", "```powershell",
".\\.venv\\Scripts\\python.exe -m scripts.evaluate_scrapling_retrieval --live --allow-rendered --dataset .preview/evaluations/scrapling_retrieval_20261019/dataset_complete.json --output .preview/evaluations/scrapling_retrieval_20261019/fresh_repeat",
"```", "", "Limitation: rendering effectiveness, publisher listing discovery, the three missing selected URLs, population reliability, and full article completeness remain unestablished. The frozen sample is biased toward recoverable saved Google News metadata, so its overall success percentage is not a direct-publisher retrieval success estimate.", ""]
(OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
print(json.dumps(dict(urls=len(rows), distinct_articles=len({r['article_id'] for r in rows}), methods=all_methods,
                      selected_urls_unavailable=len(dataset['unavailable_selected']), protected_files=len(before)),indent=2))

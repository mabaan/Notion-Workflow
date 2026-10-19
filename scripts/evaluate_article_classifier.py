"""Offline baseline and explicitly budgeted classification experiment; no ingestion.

Default execution is offline. --live is a separate, explicit opt-in. Outputs are
confined to a new evaluation directory; no SeenStore/Notion client is constructed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, UTC
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import time

from dotenv import load_dotenv
import httpx
from openai import OpenAI

from research_automation.clients.article_classifier import ArticleClassifier
from research_automation.config import Settings
from research_automation.models.article import Article
from research_automation.models.classification import ClassificationInput
from research_automation.pipeline.article_classification import prepare_classification_inputs
from research_automation.pipeline.candidate_ranking import _prepare_candidate, evaluate_candidate_pool

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/article_classifier_benchmark.json"
DEFAULT_OUTPUT = ROOT / ".preview/evaluations/article_classifier_2026-10-18"
# Standard synchronous API rates per million tokens, checked 2026-10-18.
# These are application-level batches, NOT the discounted asynchronous Batch API.
PRICES = {
    "gpt-4.1-mini": dict(input=0.40, cached_input=0.10, output=1.60),
    "gpt-4.1-nano": dict(input=0.10, cached_input=0.025, output=0.40),
    "gpt-6-luna": dict(input=0.10, cached_input=0.01, cache_write=0.125, output=0.50),
}
PRICE_SOURCES = [f"https://developers.openai.com/api/docs/models/{model}" for model in PRICES]
BUDGET = dict(max_requests=6, max_reserved_tokens=160_000, max_reserved_usd=0.25)


def experiment_plan(model=None):
    if model is None:
        return [("mini-100", "gpt-4.1-mini", 100),
                ("mini-repartitioned", "gpt-4.1-mini", 18),
                ("nano-100", "gpt-4.1-nano", 100)]
    prefix = {"gpt-6-luna": "luna", "gpt-4.1-mini": "mini", "gpt-4.1-nano": "nano"}[model]
    return [(prefix + "-100", model, 100), (prefix + "-repartitioned", model, 18)]


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def state_hashes(root: Path = ROOT) -> dict:
    return {str(path.relative_to(root)): file_hash(path)
            for path in sorted((root / ".local_state").rglob("*")) if path.is_file()}


def model_input(row: dict) -> ClassificationInput:
    return ClassificationInput(
        row["article_id"], row["title"], row["snippet"], row["publisher"],
        datetime.fromisoformat(row["published_date"]) if row["published_date"] else None,
        tuple(row["source_region_hints"]),
    )


def legacy_article(row: dict) -> Article:
    metadata = model_input(row)
    return Article(
        title=metadata.title, snippet=metadata.snippet, url=row["url"], canonical_url=row["url"],
        source_name=metadata.publisher, published_date=metadata.published_date,
        source_page_id=metadata.publisher if row["registered"] else "",
        source_editorial_quality=row["source_quality"], region=list(metadata.source_region_hints),
        discovery_provider=None if row["registered"] else "historical-unregistered",
    )


def baseline(snapshot: dict) -> dict:
    settings = Settings()  # Verified equal to configured production editorial settings for this experiment.
    now = datetime.fromisoformat(snapshot["historical_as_of"])
    start = time.perf_counter()
    rows = {}
    primary = [row for row in snapshot["articles"] if row["stratum"] == "primary"]
    evaluation = evaluate_candidate_pool(
        [legacy_article(row) for row in primary], deficits=settings.weekly_region_targets,
        settings=settings, enrich=None, now=now, stop_when_qualified=False,
    )
    by_url = {result.article.url: result for result in evaluation.results}
    for row in snapshot["articles"]:
        article = legacy_article(row)
        gate = _prepare_candidate(article, settings=settings, now=now)
        result = by_url.get(article.url) if row["stratum"] == "primary" else None
        prepared = prepare_classification_inputs([legacy_article(row)], now=now)
        rows[row["article_id"]] = dict(
            objective_eligible=bool(prepared.inputs),
            objective_reason=prepared.excluded[0].reason if prepared.excluded else "",
            editorial_gate_pass=not bool(gate.rejection_reason), gate_reason=gate.rejection_reason,
            retained=bool(result and result.shortlisted), region=gate.target_region,
            region_basis=gate.region_assignment_basis,
            rank=result.metadata_rank if result else None,
            initial_six=bool(result and result.shortlisted and result.allocation_rank <= 6),
            matched_topics=gate.matched_topics,
        )
    return dict(rows=rows, latency_seconds=time.perf_counter() - start,
                settings={name: getattr(settings, name) for name in (
                    "article_freshness_days", "discovery_topics", "article_shortlist_initial_per_region",
                    "article_shortlist_max_per_region", "minimum_article_relevance_score")},
                quotas=settings.weekly_region_targets,
                method="Actual unchanged prepare/rank/allocation; enrichment disabled; all four deficits open; 8-per-region ceiling. No final queue selection simulated.")


def metric(rows: list[dict], predictions: dict, regions: dict, failed_ids=()) -> dict:
    """Borderline is uncertainty, not binary truth. Failure isn't an LLM judgment."""
    binary = [row for row in rows if row["reference"]["decision"] != "Borderline"]
    positive = {row["article_id"] for row in binary if row["reference"]["decision"] == "Relevant"}
    negative = {row["article_id"] for row in binary if row["reference"]["decision"] == "Irrelevant"}
    retained = {key for key, value in predictions.items() if value}
    failed = set(failed_ids)
    region_rows = [row for row in rows if row["reference"]["acceptable_regions"]]
    wrong_regions = [row["article_id"] for row in region_rows
                     if regions.get(row["article_id"]) not in row["reference"]["acceptable_regions"]]
    tp, fp = len(positive & retained), len(negative & retained)
    return dict(
        articles=len(rows), binary_articles=len(binary), positives=len(positive), negatives=len(negative),
        true_positives=tp, false_positives=sorted(negative & retained),
        false_negatives=sorted(positive - retained), true_negatives=len(negative - retained),
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / len(positive) if positive else None,
        borderline_total=len(rows) - len(binary),
        borderline_retained=sum(row["reference"]["decision"] == "Borderline" and row["article_id"] in retained for row in rows),
        region_checked=len(region_rows), wrong_regions=wrong_regions,
        region_accuracy=(len(region_rows) - len(wrong_regions)) / len(region_rows) if region_rows else None,
        unresolved=sorted(failed & {row["article_id"] for row in rows}),
        # Precision above is operational retention including fail-open. Do not claim editorial success on unresolved positives.
        classified_positive_coverage=len((positive & retained) - failed) / len(positive) if positive else None,
    )


class BudgetTransport(httpx.BaseTransport):
    """Reserve pessimistic bytes-as-tokens + max output BEFORE any network send.

    Reservations never refund unused tokens, so retries and timeouts remain bounded.
    The ledger is flushed before sending and after reading every response.
    """
    def __init__(self, output: Path, *, delegate=None, limits=None):
        self.output = output
        self.delegate = delegate or httpx.HTTPTransport(retries=0)
        self.limits = limits or BUDGET
        self.ledger = []
        self.reserved_tokens = 0
        self.reserved_usd = 0.0
        self.denied = 0
        self.article_ids_override = None  # Evaluation-only singleton enrichment calls.

    def handle_request(self, request):
        payload = json.loads(request.content)
        model = payload["model"]
        if model not in PRICES or request.url.host != "api.openai.com" or request.url.path != "/v1/chat/completions":
            raise ValueError("Experiment permits only verified classification requests to OpenAI")
        price = PRICES[model]
        input_reserve = len(request.content) + 1024
        output_reserve = payload["max_completion_tokens"]
        reserve = input_reserve + output_reserve
        cost = (input_reserve * max(price["input"], price.get("cache_write", 0))
                + output_reserve * price["output"]) / 1_000_000
        if (len(self.ledger) >= self.limits["max_requests"]
                or self.reserved_tokens + reserve > self.limits["max_reserved_tokens"]
                or self.reserved_usd + cost > self.limits["max_reserved_usd"]):
            self.denied += 1
            self.flush()
            return httpx.Response(400, request=request, json={"error": {
                "message": "Local evaluation budget exhausted; no network request sent.",
                "type": "invalid_request_error", "code": "evaluation_budget_exceeded"}})
        self.reserved_tokens += reserve
        self.reserved_usd += cost
        index = len(self.ledger) + 1
        record = dict(request_number=index, model=model, reserved_input_tokens=input_reserve,
                      reserved_output_tokens=output_reserve, reserved_usd=cost,
                      article_ids=(list(self.article_ids_override) if self.article_ids_override is not None else
                                   [row["article_id"] for row in json.loads(payload["messages"][1]["content"])["articles"]]),
                      status="reserved_before_send", usage=None, estimated_usd=None)
        self.ledger.append(record)
        write_json(self.output / f"requests/{index:02}.request.json", payload)  # No HTTP headers/secrets.
        self.flush()
        start = time.perf_counter()
        try:
            response = self.delegate.handle_request(request)
            response.read()
            record["status"] = response.status_code
            if response.status_code == 200:
                data = response.json()
                write_json(self.output / f"requests/{index:02}.response.json", data)
                record["returned_model"] = data.get("model")
                record["usage"] = usage = data.get("usage")
                if usage and all(type(usage.get(key)) is int for key in ("prompt_tokens", "completion_tokens")):
                    details = usage.get("prompt_tokens_details") or {}
                    cached = details.get("cached_tokens", 0)
                    # Chat Completions may omit cache-write details. For Luna,
                    # conservatively price the remaining input as cache writes.
                    written = details.get("cache_write_tokens", usage["prompt_tokens"] - cached
                                          if "cache_write" in price else 0)
                    record["cache_write_cost_assumed"] = "cache_write" in price and "cache_write_tokens" not in details
                    record["estimated_usd"] = ((usage["prompt_tokens"] - cached - written) * price["input"]
                                               + written * price.get("cache_write", price["input"])
                                               + cached * price["cached_input"] + usage["completion_tokens"] * price["output"]) / 1_000_000
            return response
        except Exception:
            record["status"] = "transport_error_usage_unknown"
            raise
        finally:
            record["latency_seconds"] = time.perf_counter() - start
            self.flush()

    def flush(self):
        write_json(self.output / "network_ledger.json", dict(
            limits=self.limits, requests=self.ledger, requests_sent=len(self.ledger),
            denied_locally=self.denied, reserved_tokens=self.reserved_tokens,
            reserved_usd=self.reserved_usd, known_estimated_usd=sum(r["estimated_usd"] or 0 for r in self.ledger),
            requests_with_unknown_cost=sum(r["estimated_usd"] is None for r in self.ledger),
        ))

    def close(self):
        self.delegate.close()


def summarize(snapshot, old, experiments):
    output = {}
    for group in ("primary", "supplemental", "diagnostic"):
        rows = [row for row in snapshot["articles"] if row["stratum"] == group]
        metrics = {}
        if group == "primary":
            metrics["deterministic"] = metric(rows, {k: r["retained"] for k, r in old["rows"].items()},
                                               {k: r["region"] for k, r in old["rows"].items()})
            metrics["deterministic_gate"] = metric(rows, {k: r["editorial_gate_pass"] for k, r in old["rows"].items()},
                                                  {k: r["region"] for k, r in old["rows"].items()})
        else:
            metrics["comparison_limit"] = "Diagnostic only: unknown dates/URLs fail shared objective prechecks. Not deterministic editorial false negatives or empirical classifier precision/recall."
            metrics["objective_exclusions"] = {row["article_id"]: old["rows"][row["article_id"]]["objective_reason"] for row in rows}
        for name, report in experiments.items():
            predictions, regions, failed = {}, {}, []
            for outcome in report["outcomes"]:
                result = outcome["classification"]
                key = outcome["article_id"]
                predictions[key] = result is None or result["decision"] != "Irrelevant"
                regions[key] = result["assigned_region"] if result else None
                if outcome["error"]:
                    failed.append(key)
            metrics[name] = metric(rows, predictions, regions, failed)
        output[group] = metrics
    base = next((name for name in experiments
                 if name.endswith("-100") and name[:-4] + "-repartitioned" in experiments), None)
    if base:
        other = base[:-4] + "-repartitioned"
        left = {r["article_id"]: r["classification"] for r in experiments[base]["outcomes"]}
        right = {r["article_id"]: r["classification"] for r in experiments[other]["outcomes"]}
        common = [key for key in left if left[key] and right.get(key)]
        output["consistency"] = dict(
            compared_runs=[base, other],
            jointly_classified=len(common),
            changed={field: [key for key in common if left[key][field] != right[key][field]]
                     for field in ("decision", "assigned_region", "relevance_score", "primary_mission_topic")},
            note="Different batch membership and another stochastic run; effects cannot be isolated. Rationales not string-compared.",
        )
    return output


def render_report(output: Path):
    """Regenerate comparison tables/metrics offline; narrative report is reviewed separately."""
    def read(name):
        return json.loads((output / name).read_text(encoding="utf-8"))

    snapshot, old = read("snapshot_reference.json"), read("deterministic.json")
    experiments = {path.stem: read(path.name) for path in sorted(output.glob("*.json"))
                   if path.stem.endswith(("-100", "-repartitioned"))}
    metrics = summarize(snapshot, old, experiments)
    write_json(output / "metrics.json", metrics)
    by_id = {row["article_id"]: row for row in snapshot["articles"]}
    results = {name: {row["article_id"]: row["classification"] for row in report["outcomes"]}
               for name, report in experiments.items()}
    ranks = {}
    for name, outcomes in results.items():
        ranks[name], buckets = {}, {}
        for key, result in outcomes.items():
            if by_id[key]["stratum"] == "primary" and result and result["decision"] != "Irrelevant":
                buckets.setdefault(result["assigned_region"], []).append(key)
        for keys in buckets.values():
            for rank, key in enumerate(sorted(keys, key=lambda key: (
                -outcomes[key]["relevance_score"], -(by_id[key]["source_quality"] or 0),
                -datetime.fromisoformat(by_id[key]["published_date"]).timestamp(), key)), 1):
                ranks[name][key] = rank
    write_json(output / "diagnostic_ranks.json", ranks)

    def cell(value):
        return str(value).replace("|", "&#124;").replace("\n", " ")

    lines = ["# Reproducible metadata comparison", "",
             "This file is generated offline. The separately authored report.md interprets the captured experiment.", "",
             "Primary metrics exclude supplements, user scenarios and borderline reference labels.", "",
             "| Method | TP | FP | FN | Precision | Recall | Region correct / checked |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for name, result in metrics["primary"].items():
        def pct(value):
            return f"{value * 100:.1f}%" if value is not None else "n/a"
        lines.append(f"| {name} | {result['true_positives']} | {len(result['false_positives'])} | {len(result['false_negatives'])} | {pct(result['precision'])} | {pct(result['recall'])} | {result['region_checked'] - len(result['wrong_regions'])}/{result['region_checked']} |")
    for stratum in ("primary", "supplemental", "diagnostic"):
        lines += ["", f"## {stratum}", "",
                  "Legacy: R=retained, X=excluded/deferred. LLM: decision, relevance, region, diagnostic rank. Unknown dates remain null. Diagnostic ranks are not production queue scores.", "",
                  "| ID / title | Reference / acceptable regions | Legacy decision / region / rank | " + " | ".join(experiments) + " |",
                  "|---|---|---|" + "---|" * len(experiments)]
        for row in snapshot["articles"]:
            if row["stratum"] != stratum:
                continue
            key, legacy = row["article_id"], old["rows"][row["article_id"]]
            ref = row["reference"]
            reason = legacy['gate_reason'] or ('shortlist ceiling' if not legacy['retained'] else '')
            cells = [f"{key}: {row['title']}", f"{ref['decision']}; {', '.join(ref['acceptable_regions']) or 'not scored'}",
                     f"{'R' if legacy['retained'] else 'X'} ({reason}); {legacy['region'] or 'Unclear'}; rank {legacy['rank'] or '-'}"]
            for name, outcomes in results.items():
                result = outcomes.get(key)
                cells.append(f"{result['decision']} {result['relevance_score']}; {result['assigned_region']}; rank {ranks[name].get(key, '-')}" if result else "UNRESOLVED")
            lines.append("| " + " | ".join(map(cell, cells)) + " |")
    lines += ["", "## Reference and model rationales", ""]
    for row in snapshot["articles"]:
        key = row["article_id"]
        lines += [f"**{key}**: {row['reference']['rationale']}", ""]
        for name, outcomes in results.items():
            result = outcomes.get(key)
            lines += [f"- {name}: {result['justification'] if result else 'Unresolved; no invented judgment.'}"]
        lines += [""]
    (output / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--report-only", action="store_true", help="Analyze captured results without any API calls")
    parser.add_argument("--model", choices=list(PRICES), help="Use this model for both batch configurations")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or (ROOT / ".preview/evaluations").resolve() not in output.parents:
        parser.error("Output must be a child of .preview/evaluations")
    if args.report_only:
        if args.live:
            parser.error("--report-only and --live cannot be combined")
        render_report(output)
        print(f"Rendered {output / 'comparison.md'}; no API calls")
        return
    if (output / "manifest.json").exists():
        parser.error("Use a new output directory; existing experiments are immutable, no accidental repeat spend")
    snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))
    plan = experiment_plan(args.model)
    before = state_hashes()
    prompt = (Settings().prompt_directory / "article_classification.txt").read_text(encoding="utf-8")
    manifest = dict(created_utc=datetime.now(UTC).isoformat(), live=args.live,
                    git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    snapshot_sha256=file_hash(FIXTURE), prompt_sha256=sha256(prompt.encode()).hexdigest(),
                    classifier_sha256=file_hash(ROOT / "src/research_automation/clients/article_classifier.py"),
                    reference_frozen_before_live=True, pricing=PRICES, pricing_sources=PRICE_SOURCES,
                    pricing_checked_date="2026-10-18", budget=BUDGET,
                    state_before=before, settings_source="Settings defaults; verified against local environment before experiment",
                    experiment_plan=plan,
                    model_lifecycle=("GPT-6 Luna profile verified against official model documentation on 2026-10-18."
                                     if args.model == "gpt-6-luna" else
                                     "Official pages label the GPT-4.1 families Deprecated; availability is tested here."))
    write_json(output / "manifest.json", manifest)
    write_json(output / "snapshot_reference.json", snapshot)
    (output / "prompt.txt").write_text(prompt, encoding="utf-8")
    old = baseline(snapshot)
    write_json(output / "deterministic.json", old)
    experiments = {}
    try:
        if args.live:
            load_dotenv(ROOT / ".env")
            key = os.environ.get("OPENAI_API_KEY", "")
            if not key:
                raise ValueError("OPENAI_API_KEY is not configured")
            transport = BudgetTransport(output)
            with OpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0,
                        http_client=httpx.Client(transport=transport)) as client:
                inputs = [model_input(row) for row in snapshot["articles"]]
                # First request starts at 100; actual partial batch = available pool.
                # Repartitioning tests context sensitivity without inventing 100 samples.
                for name, model, batch in plan:
                    settings = replace(Settings(), classification_model=model, classification_batch_size=batch,
                                       classification_max_output_tokens=16_384 if model == "gpt-6-luna" else 12_288,
                                       classification_timeout_seconds=120 if model == "gpt-6-luna" else 60)
                    start = time.perf_counter()
                    result = ArticleClassifier(settings, client=client).classify(inputs)
                    report = asdict(result)
                    report.update(latency_seconds=time.perf_counter() - start, batch_size=batch,
                                  reasoning_effort="medium" if model == "gpt-6-luna" else None,
                                  max_output_tokens=settings.classification_max_output_tokens,
                                  request_count=result.request_count, usage=result.token_usage,
                                  requests_without_usage=result.requests_without_usage)
                    experiments[name] = report
                    write_json(output / f"{name}.json", report)
                    print(f"{name}: {len(inputs)} outcomes, {len(result.failed_ids)} unresolved, {result.request_count} attempts; {report['latency_seconds']:.2f}s", flush=True)
    finally:
        manifest["state_after"] = state_hashes()
        manifest["persistent_state_unchanged"] = manifest["state_after"] == before
        write_json(output / "manifest.json", manifest)
        write_json(output / "metrics.json", summarize(snapshot, old, experiments))
        if experiments:
            render_report(output)
    print(f"Saved evaluation: {output}", flush=True)


if __name__ == "__main__":
    main()

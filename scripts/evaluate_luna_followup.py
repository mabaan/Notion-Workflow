"""Frozen 100-article batch/repeat evaluation plus paired enrichment and Veal probes.

Collection and reference annotation must precede --live. Default: analyze captured
results offline. This runner never collects feeds or queries/writes Notion.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

from dotenv import load_dotenv
import httpx
from openai import OpenAI

from scripts.evaluate_article_classifier import (
    ROOT, FIXTURE, PRICES, BudgetTransport, baseline, file_hash, legacy_article,
    metric, model_input, state_hashes, summarize, write_json,
)
from scripts.evaluate_enriched_selection import evaluate_paths
from research_automation.clients.article_classifier import ArticleClassifier
from research_automation.clients.llm_client import LlmClient
from research_automation.config import Settings

DEFAULT_OUTPUT = ROOT / ".preview/evaluations/luna_followup_2026-10-19"
LIMITS = dict(max_requests=30, max_reserved_tokens=700_000, max_reserved_usd=0.25)
PLAN = (("fresh100-a", 100), ("fresh100-b", 100), ("fresh50", 50), ("historical-repeat", 100))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_enricher(create):
    # Real unchanged production prompt renderer/parser; only API transport is injected.
    client = LlmClient("openai", "gpt-6-luna", "evaluation-transport-injected",
                       Settings().prompt_directory, Settings().discovery_topics)
    client.client.close()
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client


def compare_runs(left, right):
    left = {r["article_id"]: r["classification"] for r in left["outcomes"]}
    right = {r["article_id"]: r["classification"] for r in right["outcomes"]}
    keys = sorted(k for k in left.keys() & right.keys() if left[k] and right[k])
    changes = {field: [k for k in keys if left[k][field] != right[k][field]]
               for field in ("decision", "assigned_region", "relevance_score", "primary_mission_topic")}
    changes["retention"] = [k for k in keys if (left[k]["decision"] != "Irrelevant") != (right[k]["decision"] != "Irrelevant")]
    return dict(jointly_classified=len(keys), changed=changes)


def preflight(snapshot, historical):
    """Estimate exact serialized request reservations without sending anything."""
    ids = [row["article_id"] for row in snapshot["articles"]]
    panel = snapshot["enrichment_panel_ids"]
    if len(ids) != 100 or len(set(ids)) != 100:
        raise ValueError("The full-batch experiment requires exactly 100 distinct articles")
    if len(panel) != 20 or len(set(panel)) != 20 or not set(panel) <= set(ids):
        raise ValueError("The fixed enrichment panel requires 20 distinct snapshot IDs")
    payloads = []
    with OpenAI(api_key="offline-preflight") as api:
        for name, batch_size in PLAN:
            rows = historical["articles"] if name == "historical-repeat" else snapshot["articles"]
            settings = replace(Settings(), classification_model="gpt-6-luna", classification_batch_size=batch_size,
                               classification_timeout_seconds=180,
                               classification_max_output_tokens=16_384 if name == "historical-repeat" else 32_768)
            classifier = ArticleClassifier(settings, client=api)
            inputs = sorted(map(model_input, rows), key=lambda row: row.article_id)
            for offset in range(0, len(inputs), batch_size):
                group = inputs[offset:offset + batch_size]
                arguments = classifier._request_arguments(group)
                if not classifier._fits(group, arguments):
                    raise ValueError("Planned full batches do not fit; revise pre-registered experiment before sending")
                payloads.append(arguments)

    def capture(**arguments):
        arguments.update(max_completion_tokens=4096, service_tier="default")
        payloads.append(arguments)
        # Preflight-only dummy, never persisted/interpreted as a model outcome.
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(dict(story_type="other", is_new_development="unclear")),
        ))])

    enricher = make_enricher(capture)
    by_id = {row["article_id"]: row for row in snapshot["articles"]}
    for key in snapshot["enrichment_panel_ids"]:
        enricher.enrich_article(legacy_article(by_id[key]))
    veal = next(row for row in historical["articles"] if row["article_id"] == "oct16-veal")
    for _ in range(4):
        enricher.enrich_article(legacy_article(veal))
    sizes = [len(httpx.Request("POST", "https://api.openai.com/v1/chat/completions", json=payload).content)
             for payload in payloads]
    reserved_tokens = sum(size + 1024 + payload["max_completion_tokens"] for size, payload in zip(sizes, payloads))
    reserved_usd = sum(((size + 1024) * .125 + payload["max_completion_tokens"] * .50) / 1e6
                       for size, payload in zip(sizes, payloads))
    if (len(payloads) > LIMITS["max_requests"] or reserved_tokens > LIMITS["max_reserved_tokens"]
            or reserved_usd > LIMITS["max_reserved_usd"]):
        raise ValueError("Pre-registered experiment exceeds its hard budget")
    return dict(planned_requests=len(payloads), reserved_tokens=reserved_tokens, reserved_usd=reserved_usd)


def analyze(output):
    snapshot, old = read(output / "snapshot_reference.json"), read(output / "deterministic.json")
    current = {name: read(output / (name + ".json")) for name, _ in PLAN
               if name != "historical-repeat" and (output / (name + ".json")).exists()}
    metrics = summarize(snapshot, old, current)
    consistency = {}
    if "fresh100-a" in current and "fresh100-b" in current:
        consistency["same_batch_repeat"] = compare_runs(current["fresh100-a"], current["fresh100-b"])
    if "fresh100-a" in current and "fresh50" in current:
        consistency["100_vs_50"] = compare_runs(current["fresh100-a"], current["fresh50"])
    historical_path = output / "historical-repeat.json"
    if historical_path.exists():
        previous = ROOT / ".preview/evaluations/article_classifier_luna_2026-10-18/luna-100.json"
        consistency["historical_same_batch_repeat"] = compare_runs(read(previous), read(historical_path))
    metrics["cohorts"] = {}
    for cohort in ("publisher_balanced", "mission_oversample"):
        subset = [row for row in snapshot["articles"] if row["cohort"] == cohort]
        values = {"deterministic": metric(subset, {k: v["retained"] for k, v in old["rows"].items()},
                                         {k: v["region"] for k, v in old["rows"].items()})}
        for name, report in current.items():
            outcomes = report["outcomes"]
            values[name] = metric(subset, {o["article_id"]: o["classification"] is None or o["classification"]["decision"] != "Irrelevant" for o in outcomes},
                                  {o["article_id"]: (o["classification"] or {}).get("assigned_region") for o in outcomes},
                                  [o["article_id"] for o in outcomes if o["error"]])
        metrics["cohorts"][cohort] = values
    write_json(output / "metrics.json", metrics)
    write_json(output / "consistency.json", consistency)
    if (output / "panel_enrichment.json").exists():
        panel = {**snapshot, "articles": [row for row in snapshot["articles"] if row["article_id"] in snapshot["enrichment_panel_ids"]]}
        write_json(output / "panel_comparison.json", evaluate_paths(panel, old, current, read(output / "panel_enrichment.json")))
    if (output / "veal_repeats.json").exists():
        probes = read(output / "veal_repeats.json")
        previous = read(ROOT / ".preview/evaluations/article_classifier_luna_2026-10-18/enrichment/outcomes.json")["oct16-veal"]
        cases = [previous, *probes]
        scores = [case["enrichment"]["relevance_score"] if case["enrichment"] else None for case in cases]
        write_json(output / "veal_stability.json", dict(
            relevance_scores=scores, significance_scores=[case["enrichment"]["editorial_significance"] if case["enrichment"] else None for case in cases],
            qualified=sum(score is not None and score >= 4 for score in scores),
            unresolved=sum(score is None for score in scores), total=len(scores),
            note="One previous and four new calls with identical metadata/prompt and medium reasoning; no voting or production prompt changes.",
        ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / ".preview/evaluations").resolve() not in output.parents:
        parser.error("Output must be a child of .preview/evaluations")
    if not args.live:
        analyze(output)
        print("Replayed follow-up analysis offline")
        return
    if (output / "manifest.json").exists():
        parser.error("Experiment already exists; no accidental repeat spend")
    snapshot, historical = read(output / "snapshot_reference.json"), read(FIXTURE)
    estimate = preflight(snapshot, historical)
    write_json(output / "preflight.json", estimate)
    manifest = dict(model="gpt-6-luna", reasoning_effort="medium", limits=LIMITS, plan=PLAN,
                    snapshot_sha256=file_hash(output / "snapshot_reference.json"), historical_sha256=file_hash(FIXTURE),
                    classifier_prompt_sha256=file_hash(Settings().prompt_directory / "article_classification.txt"),
                    enrichment_prompt_sha256=file_hash(Settings().prompt_directory / "article_enrichment.txt"),
                    runner_sha256=file_hash(Path(__file__)), reference_frozen_before_live=True,
                    pricing=PRICES["gpt-6-luna"], pricing_verified_date="2026-10-19", state_before=state_hashes())
    write_json(output / "manifest.json", manifest)
    write_json(output / "deterministic.json", baseline(snapshot))
    load_dotenv(ROOT / ".env")
    start = time.perf_counter()
    try:
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured")
        transport = BudgetTransport(output, limits=LIMITS)
        with OpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0, timeout=180,
                    http_client=httpx.Client(transport=transport)) as api:
            for name, batch in PLAN:
                data = historical if name == "historical-repeat" else snapshot
                settings = replace(Settings(), classification_model="gpt-6-luna", classification_batch_size=batch,
                                   classification_timeout_seconds=180,
                                   classification_max_output_tokens=16_384 if name == "historical-repeat" else 32_768)
                before = time.perf_counter()
                result = ArticleClassifier(settings, client=api).classify([model_input(row) for row in data["articles"]])
                report = asdict(result)
                report.update(latency_seconds=time.perf_counter() - before, usage=result.token_usage,
                              request_count=result.request_count, batch_size=batch)
                write_json(output / (name + ".json"), report)
                print(f"{name}: {len(result.outcomes)} outcomes; {len(result.failed_ids)} unresolved; {report['latency_seconds']:.2f}s", flush=True)

            def create(**arguments):
                arguments.update(max_completion_tokens=4096, service_tier="default")
                return api.chat.completions.create(**arguments)

            enricher = make_enricher(create)

            def enrich(row):
                transport.article_ids_override = (row["article_id"],)
                before = time.perf_counter()
                outcome = dict(article_id=row["article_id"], enrichment=None, error=None)
                try:
                    outcome["enrichment"] = asdict(enricher.enrich_article(legacy_article(row)))
                except Exception as exc:
                    outcome["error"] = type(exc).__name__
                outcome["latency_seconds"] = time.perf_counter() - before
                return outcome

            panel = {}
            by_id = {row["article_id"]: row for row in snapshot["articles"]}
            for index, article_id in enumerate(snapshot["enrichment_panel_ids"], 1):
                panel[article_id] = enrich(by_id[article_id])
                write_json(output / "panel_enrichment.json", panel)
                print(f"Paired panel {index}/20: {'unresolved' if panel[article_id]['error'] else 'OK'}", flush=True)
            veal = next(row for row in historical["articles"] if row["article_id"] == "oct16-veal")
            repeats = []
            for index in range(4):
                repeats.append(enrich(veal))
                write_json(output / "veal_repeats.json", repeats)
                print(f"Veal repeat {index + 1}/4: {'unresolved' if repeats[-1]['error'] else 'OK'}", flush=True)
    finally:
        manifest.update(latency_seconds=time.perf_counter() - start, state_after=state_hashes())
        manifest["persistent_state_unchanged"] = manifest["state_before"] == manifest["state_after"]
        write_json(output / "manifest.json", manifest)
        analyze(output)


if __name__ == "__main__":
    main()

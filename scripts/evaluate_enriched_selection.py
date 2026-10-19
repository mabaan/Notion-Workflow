"""Compare legacy and Luna screening with identical, cached Luna enrichments.

Run only on a captured classifier experiment. --live authorizes the bounded,
metadata-only enrichment phase; otherwise replay captured results offline.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

from dotenv import load_dotenv
import httpx
from openai import OpenAI

from scripts.evaluate_article_classifier import (
    ROOT, BudgetTransport, file_hash, legacy_article, metric, state_hashes, write_json,
)
from research_automation.clients.llm_client import LlmClient
from research_automation.config import Settings
from research_automation.models.article import EnrichedArticle
from research_automation.models.candidate import CandidateResult
from research_automation.pipeline.candidate_ranking import calculate_queue_score
from research_automation.pipeline.selection import WeeklyQueueState, select_final_candidates
from research_automation.utils.urls import clean_url, url_hostname

DEFAULT_SOURCE = ROOT / ".preview/evaluations/article_classifier_luna_2026-10-18"
MODEL = "gpt-6-luna"
ENRICHMENT_BUDGET = dict(max_requests=25, max_reserved_tokens=320_000, max_reserved_usd=0.20)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def retained_sets(snapshot, old, experiments):
    primary = {row["article_id"] for row in snapshot["articles"] if row["stratum"] == "primary"}
    retained = {"deterministic": {key for key in primary if old["rows"][key]["retained"]}}
    for name, report in experiments.items():
        retained[name] = {row["article_id"] for row in report["outcomes"]
                          if row["article_id"] in primary and (row["classification"] is None
                          or row["classification"]["decision"] != "Irrelevant")}
    return retained


def evaluate_paths(snapshot, old, experiments, enrichments):
    """Apply unchanged relevance thresholds, queue weights and final constraints."""
    settings = Settings()
    rows = [row for row in snapshot["articles"] if row["stratum"] == "primary"]
    retained = retained_sets(snapshot, old, experiments)
    classifications = {name: {o["article_id"]: o["classification"] for o in report["outcomes"]}
                       for name, report in experiments.items()}
    paths = {}
    for name, keys in retained.items():
        candidates, decisions, qualified, regions, failed = [], {}, {}, {}, []
        for row in rows:
            key = row["article_id"]
            region = (old["rows"][key]["region"] if name == "deterministic" else
                      (classifications[name].get(key) or {}).get("assigned_region"))
            regions[key] = region
            required = settings.minimum_article_relevance_score if row["registered"] else 5
            outcome = enrichments.get(key, {})
            payload = outcome.get("enrichment")
            decision = dict(screen_retained=key in keys, required_relevance=required, region=region,
                            enrichment_relevance=None, editorial_significance=None, queue_score=None,
                            qualified=False, status="screen rejected", final_winner=False)
            decisions[key] = decision
            qualified[key] = False
            if key not in keys:
                continue
            if payload is None:
                decision["status"] = "enrichment unresolved; retained for later assessment"
                qualified[key] = True  # Operational uncertainty is not an editorial rejection.
                failed.append(key)
                continue
            enriched = EnrichedArticle(**payload)
            score = calculate_queue_score(enriched.relevance_score, row["source_quality"], enriched.editorial_significance)
            passes = enriched.relevance_score >= required
            decision.update(enrichment_relevance=enriched.relevance_score,
                            editorial_significance=enriched.editorial_significance, queue_score=score,
                            qualified=passes, status="qualified" if passes else "below unchanged relevance threshold")
            qualified[key] = passes
            if not passes:
                continue
            if region not in settings.weekly_region_targets:
                decision["status"] = "qualified but geography unresolved; no fabricated quota assignment"
                continue
            article = legacy_article(row)
            article.canonical_url = clean_url(article.canonical_url)
            article.publisher_key = article.source_page_id or url_hostname(article.canonical_url)
            candidates.append(CandidateResult(
                article=article, enrichment=enriched, target_region=region, queue_score=score,
                source_quality=row["source_quality"], candidate_id=key, required_relevance_score=required,
            ))
        final = select_final_candidates(
            candidates, weekly_state=WeeklyQueueState(), targets=settings.weekly_region_targets,
            run_limit=settings.max_articles_per_run, publisher_cap=settings.max_articles_per_publisher_per_week,
        )
        winner_ids = [candidate.candidate_id for candidate in final.winners]
        for key in winner_ids:
            decisions[key]["final_winner"] = True
        paths[name] = dict(
            screened_in=sorted(keys), qualified_ids=sorted(k for k, v in qualified.items() if v and k not in failed),
            unresolved=failed, rows=decisions, final_winner_ids=winner_ids,
            qualified_metrics=metric(rows, qualified, regions, failed),
            final_metrics=metric(rows, {key: key in winner_ids for key in qualified}, regions, failed),
            final_ranking=[dict(article_id=c.candidate_id, region=c.target_region, queue_score=c.queue_score)
                           for c in sorted(candidates, key=lambda c: (-c.queue_score, c.candidate_id))],
            shortages=final.shortages, rejected_by_constraint=final.rejected_by_constraint,
        )
    return dict(paths=paths, method="Identical metadata-only Luna enrichment reused by ID across both screens. Existing 4/5 relevance thresholds, 70/20/10 weights, quotas, publisher cap and event suppression. Empty historical weekly state; no Notion reads or writes.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    if (ROOT / ".preview/evaluations").resolve() not in source.parents:
        parser.error("Source must be a child of .preview/evaluations")
    output = source / "enrichment"
    snapshot, old = read(source / "snapshot_reference.json"), read(source / "deterministic.json")
    experiments = {path.stem: read(path) for path in sorted(source.glob("luna-*.json"))}
    if not experiments:
        parser.error("Captured Luna classifier outputs required")
    retained = retained_sets(snapshot, old, experiments)
    union = sorted(set().union(*retained.values()))
    results_path = output / "outcomes.json"
    if not args.live:
        write_json(output / "comparison.json", evaluate_paths(snapshot, old, experiments, read(results_path)))
        print("Replayed enrichment comparison offline")
        return
    if (output / "manifest.json").exists():
        parser.error("Enrichment experiment already exists; replay offline to avoid repeated spend")
    previous = read(source / "network_ledger.json")
    limits = {**ENRICHMENT_BUDGET, "max_reserved_usd": min(0.20, max(0, 0.25 - previous["reserved_usd"]))}
    manifest = dict(
        model=MODEL, reasoning_effort="medium", max_completion_tokens=4096, limits=limits,
        combined_limits=dict(max_requests=31, max_reserved_tokens=480_000, max_reserved_usd=0.25),
        article_ids=union, primary_only=True, state_before=state_hashes(),
        snapshot_sha256=file_hash(source / "snapshot_reference.json"),
        enrichment_prompt_sha256=file_hash(Settings().prompt_directory / "article_enrichment.txt"),
        screening_retained={name: sorted(keys) for name, keys in retained.items()},
        fairness="One enrichment per union ID; original identical source-region hints, not screen-assigned regions, supplied to the LLM. Full text unavailable in both paths. Reused by ID, no positional matching.",
        qualification="Registered sources need 4, unregistered 5; no lower thresholds or altered significance rules.",
    )
    write_json(output / "manifest.json", manifest)
    (output / "article_enrichment.txt").write_text(
        (Settings().prompt_directory / "article_enrichment.txt").read_text(encoding="utf-8"), encoding="utf-8")
    results = {}
    start = time.perf_counter()
    try:
        load_dotenv(ROOT / ".env")
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured")
        transport = BudgetTransport(output, limits=limits)
        with OpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0, timeout=120,
                    http_client=httpx.Client(transport=transport)) as api:
            # Inject only evaluation limits; use the unchanged enrichment renderer/parser.
            def create_limited(**arguments):
                arguments.update(max_completion_tokens=4096, service_tier="default")
                return api.chat.completions.create(**arguments)

            enricher = LlmClient("openai", MODEL, key, Settings().prompt_directory, Settings().discovery_topics)
            enricher.client.close()
            enricher.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_limited)))
            rows = {row["article_id"]: row for row in snapshot["articles"]}
            for index, article_id in enumerate(union, 1):
                transport.article_ids_override = (article_id,)
                item_start = time.perf_counter()
                outcome = dict(article_id=article_id, enrichment=None, error=None)
                try:
                    outcome["enrichment"] = asdict(enricher.enrich_article(legacy_article(rows[article_id])))
                except Exception as exc:
                    # Preserve every failure for both paths; never persist raw API errors/secrets.
                    outcome["error"] = type(exc).__name__
                outcome["latency_seconds"] = time.perf_counter() - item_start
                results[article_id] = outcome
                write_json(results_path, results)
                print(f"Enriched {index}/{len(union)}: {article_id}; {'unresolved' if outcome['error'] else 'OK'}", flush=True)
    finally:
        manifest.update(state_after=state_hashes(), latency_seconds=time.perf_counter() - start)
        manifest["persistent_state_unchanged"] = manifest["state_before"] == manifest["state_after"]
        write_json(output / "manifest.json", manifest)
        write_json(output / "comparison.json", evaluate_paths(snapshot, old, experiments, results))
    print(f"Saved {output}", flush=True)


if __name__ == "__main__":
    main()

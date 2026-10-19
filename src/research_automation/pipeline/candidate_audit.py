"""Local, metadata-only ingestion diagnostics; never an ingestion-state store."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from dataclasses import asdict
import json
from pathlib import Path
from statistics import median
from uuid import uuid4

from research_automation.utils.hashing import build_url_hash
from research_automation.utils.urls import url_hostname
from research_automation.pipeline.direct_site_discovery import acquisition_method
from research_automation.utils.evidence import is_feed_content


def _canonical_id(url):
    try:
        return build_url_hash(url) if url_hostname(url) else None
    except ValueError:
        return None


def _decision_stage(result, selected: bool, *, fallback_enabled: bool = False) -> str:
    reason = result.rejection_reason
    if selected:
        return "final_selection"
    if fallback_enabled and result.fallback_eligible:
        return "fallback_qualified_not_selected"
    if result.objective_cleanup_reason:
        return "objective_cleanup_rejection"
    if reason == "Luna classified irrelevant":
        return "luna_classification_rejection"
    if result.editorial_rejection_reason:
        return "editorial_scope_rejection"
    if result.classification_error and not result.enrichment_attempted:
        return "classification_unresolved_deferred"
    if reason == "geography unresolved after enrichment":
        return "geography_unresolved"
    if reason == "duplicate URL":
        return "duplicate_before_enrichment"
    if reason in {"outside geographic mandate", "no exact target region"}:
        return "geography_routing_rejection"
    if reason.startswith("relevance below"):
        return "llm_relevance_rejection" if result.article.source_page_id else "unregistered_publisher_threshold_rejection"
    if reason.startswith("enrichment failed:"):
        return "llm_enrichment_failure"
    if reason in {"shortlist ceiling", "shortlist deferred", "enrichment budget exhausted"} or reason.startswith("assessment deferred;"):
        return "deferred"
    if reason in {"enrichment disabled", "LLM assessment disabled"}:
        return "enrichment_disabled"
    if reason == "regional target already complete":
        return "regional_quota_complete"
    return "qualified_not_selected" if result.eligible else "metadata_rejection"


def acquisition_metrics(report) -> dict:
    """Count candidate identities once across phases, preserving raw statuses."""
    groups = defaultdict(list)
    for result in report.evaluation.results:
        groups[result.candidate_id or str(id(result.article))].append(result)
    methods = ("rss", "google_news_rss", "direct_site", "discovery_fallback")

    def empty():
        return dict(candidates=0, luna_attempted=0, enrichment_attempted=0, enriched=0,
                    retriever_attempted=0, retriever_extracted=0, retrieval_statuses={}, selected=0)

    by_method, by_publisher = {method: empty() for method in methods}, {}
    winners = {id(result) for result in report.selection.winners}
    for results in groups.values():
        result = max(results, key=lambda r: (r.enrichment_attempted, r.classification_attempted, not bool(r.objective_cleanup_reason)))
        article = result.article
        method = acquisition_method(article)
        counters = [by_method.setdefault(method, empty())]
        if method == "direct_site":
            counters.append(by_publisher.setdefault(article.source_name, empty()))
        status = article.evidence_retrieval_status
        for counts in counters:
            counts["candidates"] += 1
            counts["luna_attempted"] += int(any(r.classification_attempted for r in results))
            counts["enrichment_attempted"] += int(any(r.enrichment_attempted for r in results))
            counts["enriched"] += int(any(r.enrichment is not None for r in results))
            counts["retriever_attempted"] += int(status != "not_attempted" and not is_feed_content(status))
            counts["retriever_extracted"] += int(status == "extracted")
            counts["retrieval_statuses"][status] = counts["retrieval_statuses"].get(status, 0) + 1
            counts["selected"] += int(any(id(r) in winners for r in results))
    return {"by_method": by_method, "direct_by_publisher": by_publisher}


def google_news_resolution_metrics(report) -> dict:
    """Count input identities once; separate actual requests from cached/skipped work.

    'Extracted' is the existing retriever's outcome, not proof of a complete or
    independently supported body. No second fetch is performed for a baseline.
    """
    groups = defaultdict(list)
    for result in report.evaluation.results:
        groups[result.candidate_id or str(id(result.article))].append(result)
    rows = []
    for results in groups.values():
        result = max(results, key=lambda r: (r.enrichment_attempted, bool(r.article.google_news_resolution)))
        if result.article.google_news_resolution:
            rows.append((result.article.google_news_resolution, result.article,
                         any(r.enrichment_attempted for r in results)))
    latencies = [info["latency_seconds"] for info, _, _ in rows if info["attempted"]]

    def evidence_bucket(article):
        status = article.evidence_retrieval_status
        return "publisher_extracted" if status == "extracted" else ("feed_content" if is_feed_content(status) else "metadata_only")

    selected = Counter(evidence_bucket(w.article) for w in report.selection.winners)
    resolved_selected = Counter(evidence_bucket(w.article) for w in report.selection.winners
                                if w.article.google_news_resolution.get("status") == "resolved")
    return {
        "enabled": getattr(report, "google_news_url_resolution_enabled", False),
        "wrappers_reaching_retrieval": len(rows),
        "wrappers_reaching_enrichment": sum(enriched for _, _, enriched in rows),
        "attempted": sum(info["attempted"] for info, _, _ in rows),
        "resolved": sum(info["status"] == "resolved" for info, _, _ in rows),
        "failed": sum(info["status"] != "resolved" for info, _, _ in rows),
        "rate_limited": sum(info["status"] == "rate_limited" for info, _, _ in rows),
        "google_429_responses": sum(info["http_429_count"] for info, _, _ in rows),
        "request_count": sum(info["request_count"] for info, _, _ in rows),
        "cache_hits": sum(info["cache_hit"] for info, _, _ in rows),
        "skipped_after_resolution_cap": sum(info["failure_reason"] == "resolution_attempt_budget_exhausted"
                                            for info, _, _ in rows),
        "median_latency_seconds": round(median(latencies), 3) if latencies else None,
        "publisher_access_refusals": sum(info["status"] == "resolved" and
            article.evidence_retrieval_status == "blocked" for info, article, _ in rows),
        "evidence_transitions": dict(Counter(
            info["evidence_status_before"] + " -> " + info["evidence_status_after"] for info, _, _ in rows)),
        "publisher_bodies_recovered": sum(info["status"] == "resolved" and
            article.evidence_retrieval_status == "extracted" for info, article, _ in rows),
        "supported_article_bodies_recovered": None,
        "body_evidence_basis": "Raw ArticleRetriever extracted status; completeness and support are unverified.",
        "baseline_note": "Before is the stored pre-retrieval status, not a control wrapper fetch. No causal uplift measured.",
        "selected_evidence": {key: selected[key] for key in ("publisher_extracted", "feed_content", "metadata_only")},
        "selected_resolved_evidence": {key: resolved_selected[key] for key in ("publisher_extracted", "feed_content", "metadata_only")},
    }


def build_candidate_audit(report) -> dict:
    """Keep phase observations separate from unique input-URL identities."""

    winner_ids = {id(winner) for winner in report.selection.winners}
    fallback_enabled = getattr(report, "selection_mode", "deterministic") == "luna"
    rows = []
    phases_by_id: dict[str, set[str]] = defaultdict(set)
    counts = defaultdict(Counter)
    for result in report.evaluation.results:
        article = result.article
        enriched = result.enrichment
        selected = id(result) in winner_ids
        decision_stage = _decision_stage(result, selected, fallback_enabled=fallback_enabled)
        reason = result.rejection_reason
        fallback_qualified = fallback_enabled and result.fallback_eligible
        # Provider errors can contain request details; retain only their category.
        if reason.startswith("enrichment failed:"):
            reason = "enrichment failed; see operational log"
        strict_rejection_reason = reason
        if selected and result.selection_tier == "fallback":
            reason = "selected via fallback: " + result.fallback_reason
        elif not selected and result.publication_failure_reason:
            reason = result.publication_failure_reason
        elif not selected and result.editorial_rejection_reason:
            reason = result.editorial_rejection_reason
        elif fallback_qualified:
            reason = result.selection_rejection_reason or "fallback qualified; no spare capacity after strict selection"
        if not reason:
            reason = "selected" if selected else (result.selection_rejection_reason or "qualified; not selected under coverage, publisher-cap or event constraints")
        classification = result.classification
        row = {
            "candidate_id": result.candidate_id,
            "canonical_id": _canonical_id(article.canonical_url),
            "title": article.title,
            "publisher": article.source_name,
            "source_type": "direct_site" if acquisition_method(article) == "direct_site" else ("discovery" if article.discovery_provider else "RSS"),
            "discovery_method": acquisition_method(article),
            "discovery_page": article.discovery_page,
            "date_provenance": article.date_provenance,
            "date_precision": article.date_precision,
            "canonical_url": article.canonical_url,
            "google_news_resolution": dict(article.google_news_resolution),
            "feed_wrapper_replaced": article.feed_wrapper_replaced,
            "discovery_origins": [
                {key: value for key, value in origin.items() if key != "snippet"}
                for origin in article.discovery_origins
            ],
            "registered_publisher": bool(article.source_page_id),
            "region": result.target_region,
            "region_assignment_basis": result.region_assignment_basis,
            "source_region_hints": result.source_region_hints,
            "objective_cleanup_reason": result.objective_cleanup_reason,
            "classification_attempted": result.classification_attempted,
            "classification_decision": classification.decision if classification else None,
            "classification_relevance": classification.relevance_score if classification else None,
            "classification_region": classification.assigned_region if classification else None,
            "classification_topic": classification.primary_mission_topic if classification else None,
            "classification_reason": classification.justification if classification else None,
            "classification_story_type": classification.story_type if classification else None,
            "classification_is_new_development": classification.is_new_development if classification else None,
            "classification_error": result.classification_error,
            "region_hint_origin": "discovery query and publisher metadata" if article.discovery_provider else "publisher metadata",
            "direct_signals": result.direct_mission_signals,
            "contextual_signals": result.contextual_signals,
            "metadata_rank": result.metadata_rank,
            "allocation_rank": result.allocation_rank,
            "ordering_basis": {
                "mission_specificity": result.mission_specificity,
                "publisher_quality": result.source_quality,
                "concrete_development": result.concrete_development,
                "published_date": article.published_date.isoformat() if article.published_date else None,
                "snippet_characters": min(len(article.snippet.strip()), 500),
            },
            "phase": result.phase,
            "shortlisted": result.shortlisted,
            "deferred": result.rejection_reason in {
                "shortlist deferred", "shortlist ceiling", "enrichment budget exhausted",
            } or result.rejection_reason.startswith("assessment deferred;"),
            "enrichment_attempted": result.enrichment_attempted,
            "enrichment_skipped": not result.enrichment_attempted,
            "enriched": enriched is not None,
            "evidence_retrieval_status": article.evidence_retrieval_status,
            "relevance": enriched.relevance_score if enriched else None,
            "story_type": getattr(enriched, "story_type", None),
            "is_new_development": getattr(enriched, "is_new_development", None),
            "editorial_scope_rejection": result.editorial_rejection_reason,
            "required_relevance_score": result.required_relevance_score,
            "editorial_significance": getattr(enriched, "editorial_significance", None),
            "significance_rationale": str(getattr(enriched, "significance_reason", "") or "")[:1000],
            "queue_score": result.queue_score if result.eligible or fallback_qualified else None,
            "publisher_rating": result.source_quality,
            "strict_qualified": result.eligible,
            "strict_rejection_reason": strict_rejection_reason,
            "fallback_qualified": fallback_qualified,
            "publication_failure_reason": result.publication_failure_reason,
            "qualified": result.eligible or fallback_qualified,
            "selected": selected,
            "selection_tier": result.selection_tier if selected else None,
            "fallback_reason": result.fallback_reason,
            "regional_overflow": result.regional_overflow if selected else False,
            "final_rejection_reason": "" if selected else reason,
            "reason": reason,
            "decision_stage": decision_stage,
            "stages": (["metadata_eligible"] if result.metadata_rank is not None else [])
            + (["luna_classification"] if result.classification_attempted else [])
            + (["actual_llm_enrichment"] if result.enrichment_attempted else [])
            + [decision_stage],
        }
        rows.append(row)
        phases_by_id[result.candidate_id].add(result.phase)
        stage = counts[(result.phase, result.target_region or "Unassigned")]
        stage["evaluated_records"] += 1
        for key in ("shortlisted", "deferred", "enrichment_attempted", "enriched", "qualified", "selected"):
            stage[key] += int(row[key])
        stage["decision_" + decision_stage] += 1

    final_by_id = {row["candidate_id"]: row for row in rows}
    unique_by_region = Counter(row["region"] or "Unassigned" for row in final_by_id.values())
    acquisition = acquisition_metrics(report)
    hybrid = getattr(report, "direct_site_discovery", {})
    return {
        "dry_run": report.dry_run,
        "selection_mode": getattr(report, "selection_mode", "deterministic"),
        "weekly_capacity": dict(getattr(report, "weekly_capacity", {})),
        "google_news_url_resolution": google_news_resolution_metrics(report),
        "acquisition_metrics": acquisition["by_method"],
        "direct_site_discovery": {
            **hybrid,
            "sources": {
                publisher: {
                    **counts,
                    **{key: 0 for key in ("candidates", "luna_attempted", "enrichment_attempted", "enriched", "retriever_attempted", "retriever_extracted", "selected")},
                    "retrieval_statuses": {},
                    **acquisition["direct_by_publisher"].get(publisher, {}),
                }
                for publisher, counts in hybrid.get("sources", {}).items()
            },
        } if hybrid else {"enabled": False},
        "enrichment_budget": getattr(report, "enrichment_budget", {}),
        "classification_reports": [
            {
                "model": classification.model,
                "request_count": classification.request_count,
                "token_usage": classification.token_usage,
                "requests_without_usage": classification.requests_without_usage,
                "unresolved_ids": classification.failed_ids,
                "split_count": classification.split_count,
                "requests": [asdict(request) for request in classification.requests],
            }
            for classification in report.evaluation.classification_reports
        ],
        "evaluation_records": len(rows),
        "unique_input_candidates": len(final_by_id),
        "unique_canonical_urls": len({row["canonical_id"] for row in rows if row["canonical_id"]}),
        "reconsidered_across_phases": sum(len(phases) > 1 for phases in phases_by_id.values()),
        "unique_candidates_by_final_region": dict(unique_by_region),
        "counts_by_phase_and_region": [
            {"phase": phase, "region": region, **stage}
            for (phase, region), stage in sorted(counts.items())
        ],
        "remaining_shortages": report.selection.shortages,
        "selection_counts": {
            **{tier: sum((winner.selection_tier or "strict") == tier for winner in report.selection.winners)
               for tier in ("strict", "fallback")},
            "total": len(report.selection.winners),
        },
        "decision_stage_counts": dict(Counter(row["decision_stage"] for row in rows)),
        "candidates": rows,
    }


def write_candidate_audit(report, directory: Path, now: datetime) -> Path:
    """Write JSON details plus a readable Markdown index for both live and dry runs."""

    audit = build_candidate_audit(report)
    directory.mkdir(parents=True, exist_ok=True)
    stem = now.strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex[:8]
    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def cell(value) -> str:
        return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    lines = [
        "# Ingestion candidate audit", "",
        f"Mode: {'dry run' if report.dry_run else 'live'}. Full metadata details: [{json_path.name}]({json_path.name}).",
        f"Strict selections: {audit['selection_counts']['strict']}; fallback selections: {audit['selection_counts']['fallback']}; total selections: {audit['selection_counts']['total']}.",
        *[f"{label}: {audit['weekly_capacity'][key]}" for label, key in (
            ("Weekly article target", "weekly_total_target"),
            ("Existing weekly total", "existing_weekly_total"),
            ("Remaining weekly capacity", "remaining_weekly_capacity"),
            ("Requested run limit", "requested_run_limit"),
            ("Effective run capacity", "effective_run_capacity"),
        ) if key in audit["weekly_capacity"]],
        "",
        f"Unique input candidates: {audit['unique_input_candidates']}; evaluation records: {audit['evaluation_records']}; reconsidered across phases: {audit['reconsidered_across_phases']}.",
        "Input identities use original URL hashes; canonical aliases are counted separately. Phase counts include reconsiderations; they are not unique article counts.",
        "",
        "| Phase | Region | Evaluated | Shortlisted | Deferred | Attempted | Enriched | Qualified | Selected |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    keys = ("phase", "region", "evaluated_records", "shortlisted", "deferred", "enrichment_attempted", "enriched", "qualified", "selected")
    for stage in audit["counts_by_phase_and_region"]:
        lines.append("| " + " | ".join(cell(stage.get(key, 0)) for key in keys) + " |")
    if audit["direct_site_discovery"].get("enabled"):
        lines += ["", "## Direct-site supplement (shadow only)", "",
                  "| Publisher | Status | Feed | Found | Recent | Headline matches | Wrappers replaced | Direct only | Duplicates removed | Luna | Enrichment | Extracted | Selected |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for publisher, counts in audit["direct_site_discovery"]["sources"].items():
            values = [publisher] + [counts.get(key, 0) for key in (
                "status", "feed_candidates_collected", "direct_candidates_discovered", "recent_direct_candidates_accepted",
                "direct_feed_headline_matches", "wrappers_replaced_by_direct_urls", "direct_only_candidates", "duplicates_removed",
                "luna_attempted", "enrichment_attempted", "retriever_extracted", "selected",
            )]
            lines.append("| " + " | ".join(cell(value) for value in values) + " |")
        lines += ["", "Acquisition counts below use unique candidate identities, not phase observations. Retrieval statuses are the existing retriever's raw outcomes, not independent proof of body completeness.", ""]
        for method, counts in audit["acquisition_metrics"].items():
            lines.append(f"- {method}: {counts}")
        lines += ["", "| Title | Method | Wrapper replaced | Canonical URL | Discovery page | Date provenance / precision |", "|---|---|---|---|---|---|"]
        for row in audit["candidates"]:
            values = (row["title"], row["discovery_method"], row["feed_wrapper_replaced"], row["canonical_url"],
                      row["discovery_page"], f"{row['date_provenance']} / {row['date_precision']}")
            lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    resolution = audit["google_news_url_resolution"]
    if resolution["enabled"]:
        lines += ["", "## Google News URL resolution", "",
                  "```json", json.dumps(resolution, ensure_ascii=False, indent=2), "```", "",
                  "| Title | Acquisition | Attempted / cache | Resolution | Publisher host | Requests / seconds | Failure | Evidence before / after |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for row in audit["candidates"]:
            info = row["google_news_resolution"]
            if not info:
                continue
            values = (row["title"], info["original_acquisition_method"],
                      f"{info['attempted']} / {info['cache_hit']}", info["status"], info["resolved_hostname"],
                      f"{info['request_count']} / {info['latency_seconds']}", info["failure_reason"],
                      f"{info['evidence_status_before']} / {info['evidence_status_after']}")
            lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    lines += ["", "Shortlist capacity counts model attempts, including failed calls; duplicates rejected before enrichment are skipped and backfilled without charging a model attempt.", "", "| Decision stage | Evaluation records |", "|---|---:|"]
    for stage, count in sorted(audit["decision_stage_counts"].items()):
        lines.append(f"| {stage} | {count} |")
    if audit["selection_mode"] == "luna":
        lines += ["", "## Luna classification and final decisions", ""]
        lines += [f"Enrichment budget / actual attempts: {audit['enrichment_budget']}", ""]
        for classification in audit["classification_reports"]:
            lines.append(
                f"Model: {classification['model']}; requests: {classification['request_count']}; "
                f"reported tokens: {classification['token_usage']}; "
                f"requests without usage: {classification['requests_without_usage']}; "
                f"unresolved IDs: {len(classification['unresolved_ids'])}."
            )
        lines += ["", "| Title | Cleanup | Classifier attempted / decision / score / region | Classifier reason / error | Classifier type / new | Shortlisted / enriched | Final relevance / significance | Final type / new | Publisher rating / queue score / region | Selection tier | Final decision | Overflow |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for row in audit["candidates"]:
            values = (
                row["title"], row["objective_cleanup_reason"],
                f"{row['classification_attempted']} / {row['classification_decision']} / {row['classification_relevance']} / {row['classification_region']}",
                f"{row['classification_reason'] or ''} / {row['classification_error'] or ''}",
                f"{row['classification_story_type']} / {row['classification_is_new_development']}",
                f"{row['shortlisted']} / {row['enrichment_attempted']}",
                f"{row['relevance']} / {row['editorial_significance']}",
                f"{row['story_type']} / {row['is_new_development']}",
                f"{row['publisher_rating']} / {row['queue_score']} / {row['region']}",
                row["selection_tier"],
                row["reason"], row["regional_overflow"],
            )
            lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    lines += ["", "| Title / publisher | Origin / registered | Region / basis | Direct / contextual signals | Metadata / allocation rank | Ordering basis | Phase | Shortlisted / deferred | Attempted | Relevance / significance | Stage / decision | Evidence / significance rationale |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in audit["candidates"]:
        values = (
            f"{row['title']} / {row['publisher']}",
            f"{row['source_type']} / {row['registered_publisher']}",
            f"{row['region']} / {row['region_assignment_basis']}",
            f"{', '.join(row['direct_signals'])} / {', '.join(row['contextual_signals'])}",
            f"{row['metadata_rank']} / {row['allocation_rank']}",
            json.dumps(row["ordering_basis"], ensure_ascii=False),
            row["phase"], f"{row['shortlisted']} / {row['deferred']}", row["enrichment_attempted"],
            f"{row['relevance']} / {row['editorial_significance']}", f"{row['decision_stage']} / {row['reason']}",
            f"{row['evidence_retrieval_status']} / {row['significance_rationale']}",
        )
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return markdown_path

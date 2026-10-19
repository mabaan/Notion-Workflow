"""Local, metadata-only ingestion diagnostics; never an ingestion-state store."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4

from research_automation.utils.hashing import build_url_hash
from research_automation.utils.urls import url_hostname


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
            "source_type": "discovery" if article.discovery_provider else "RSS",
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
    return {
        "dry_run": report.dry_run,
        "selection_mode": getattr(report, "selection_mode", "deterministic"),
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

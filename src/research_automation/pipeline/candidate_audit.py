"""Local, metadata-only ingestion diagnostics; never an ingestion-state store."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from research_automation.utils.hashing import build_url_hash
from research_automation.utils.urls import url_hostname


def _decision_stage(result, selected: bool) -> str:
    reason = result.rejection_reason
    if selected:
        return "final_selection"
    if reason == "duplicate URL":
        return "duplicate_before_enrichment"
    if reason in {"outside geographic mandate", "no exact target region"}:
        return "geography_routing_rejection"
    if reason.startswith("relevance below"):
        return "llm_relevance_rejection" if result.article.source_page_id else "unregistered_publisher_threshold_rejection"
    if reason.startswith("enrichment failed:"):
        return "llm_enrichment_failure"
    if reason in {"shortlist ceiling", "shortlist deferred"}:
        return "deferred"
    if reason == "enrichment disabled":
        return "enrichment_disabled"
    if reason == "regional target already complete":
        return "regional_quota_complete"
    return "qualified_not_selected" if result.eligible else "metadata_rejection"


def build_candidate_audit(report) -> dict:
    """Keep phase observations separate from unique input-URL identities."""

    winner_ids = {id(winner) for winner in report.selection.winners}
    rows = []
    phases_by_id: dict[str, set[str]] = defaultdict(set)
    counts = defaultdict(Counter)
    for result in report.evaluation.results:
        article = result.article
        enriched = result.enrichment
        selected = id(result) in winner_ids
        decision_stage = _decision_stage(result, selected)
        reason = result.rejection_reason
        # Provider errors can contain request details; retain only their category.
        if reason.startswith("enrichment failed:"):
            reason = "enrichment failed; see operational log"
        if not reason:
            reason = "selected" if selected else "qualified; not selected under quota, publisher-cap or event constraints"
        row = {
            "candidate_id": result.candidate_id,
            "canonical_id": build_url_hash(article.canonical_url) if url_hostname(article.canonical_url) else None,
            "title": article.title,
            "publisher": article.source_name,
            "source_type": "discovery" if article.discovery_provider else "RSS",
            "registered_publisher": bool(article.source_page_id),
            "region": result.target_region,
            "region_assignment_basis": result.region_assignment_basis,
            "source_region_hints": result.source_region_hints,
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
            "deferred": result.rejection_reason in {"shortlist deferred", "shortlist ceiling"},
            "enrichment_attempted": result.enrichment_attempted,
            "enrichment_skipped": not result.enrichment_attempted,
            "enriched": enriched is not None,
            "evidence_retrieval_status": article.evidence_retrieval_status,
            "relevance": enriched.relevance_score if enriched else None,
            "required_relevance_score": result.required_relevance_score,
            "editorial_significance": getattr(enriched, "editorial_significance", None),
            "significance_rationale": str(getattr(enriched, "significance_reason", "") or "")[:1000],
            "queue_score": result.queue_score if result.eligible else None,
            "qualified": result.eligible,
            "selected": selected,
            "reason": reason,
            "decision_stage": decision_stage,
            "stages": (["metadata_eligible"] if result.metadata_rank is not None else [])
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

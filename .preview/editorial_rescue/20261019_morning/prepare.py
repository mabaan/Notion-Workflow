"""Prepare a one-off review from existing files only; no article/network reads."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUDIT = ROOT / ".preview/ingestion_audits/20261019T003107332472Z_488d8187.json"
audit = json.loads(AUDIT.read_text(encoding="utf-8"))

# Manual editorial sampling for this evaluation, never a production filter.
# Include concrete financing/infrastructure, potentially systemic developments,
# applied-science boundaries, weak commentary controls and duplicate controls.
PREFIXES = {
    "ceecbd17a9": "Development-bank critical-minerals financing",
    "cb1f532113": "Priced UAE green-finance issuance; verify actual proceeds",
    "bfbf9ca78b": "Reported new measured forest-carbon outcome",
    "1f1ce6b603": "New investigation into commercial EV-battery supply chains",
    "7e695fc905": "Water-risk survey findings; check practical/systemic importance",
    "c05a617f4b": "Domestic poultry development; distinguish certification from capacity",
    "17f52b925d": "Three actual new feeder-bus routes; assess materiality",
    "dde400a517": "Operational rail/metro connection; assess materiality",
    "11750816d2": "Electricity-integration commentary versus actual new commitments",
    "7d90239af3": "Water commentary control",
    "dbf260aa5b": "Water-reuse membrane application versus laboratory-only work",
    "b7017705b8": "Water research opportunity versus demonstrated application",
    "761e37ea08": "Egypt food-waste study versus new practical action",
    "ce380d01e4": "Fertilizer-access programme versus general institutional advocacy",
    "0e89add423": "Egypt energy context; check age and transition relevance",
    "68631f2605": "Hormuz connectivity analysis; require new direct mission effects",
    "59be6ce377": "Food cold-chain warning versus documented operational incident",
    "be62706e9f": "Reported environmental activity versus new policy or deployment",
    "786bf02f04": "Egypt food-export explainer versus concrete production development",
    "542bd7441a": "Olive-oil waste circularity review versus commercial application",
    "3a2ef06719": "Fivefold World Bank minerals goal; possible financing-announcement overlap",
    "93a28ee21b": "$2.2bn Saudi electricity project; technology and transition role unknown",
    "f2bdbe92d2": "Quantified Dubai tree-planting plan; assess novelty and mission bridge",
    "14d300a88d": "Agritech policy calls versus adopted policies/agreements",
    "1a8bf93494": "Potentially systemic vehicle-emissions regulation; deal stage matters",
    "bb8c1feda7": "Conditional EV tariffs; distinguish from emissions-rule negotiations",
    "bdc81c0f71": "Commercial Gaza supply halt; compare existing UN/Gaza article",
    "66cb9b1af5": "Syrian farmers affected by conflict; require material production evidence",
    "973d016a7e": "Burned olive trees; require scale and distinct development",
    "52d32f3db4": "Olive-harvest feature; duplicate/novelty and conflict-relevance control",
    "6980722669": "Already-represented GERD explainer duplicate control",
}

metadata_files = [
    ROOT / ".preview/evaluations/luna_followup_2026-10-19" / name
    for name in ("collected_metadata.json", "targeted_metadata.json", "egypt_metadata.json")
]
metadata = {}
for path in metadata_files:
    for row in json.loads(path.read_text(encoding="utf-8")):
        if isinstance(row, dict) and row.get("article_id"):
            metadata.setdefault(row["article_id"], []).append((path, row))

pool = [row for row in audit["candidates"]
        if row["classification_decision"] in {"Relevant", "Borderline"}]
chosen = []
manifest = []
for prefix, inclusion_reason in PREFIXES.items():
    matches = [row for row in pool if row["candidate_id"].startswith(prefix)]
    assert len(matches) == 1, (prefix, len(matches))
    row = matches[0]
    assert not row["selected"]
    saved = metadata.get(row["candidate_id"], [])
    # Exact original-ID match only; an old snapshot does not become latest-run text.
    saved_metadata = None
    if saved:
        path, record = saved[0]
        saved_metadata = {
            "capture": "Earlier saved evaluation metadata, exact original article-ID match",
            "file": str(path.relative_to(ROOT)),
            "url": record.get("url"),
            "rss_description": record.get("snippet") or None,
            "provenance": record.get("provenance"),
            "not_latest_run_retrieved_text": True,
        }
    review_id = f"C{len(chosen)+1:02}"
    chosen.append({
        "id": review_id, "article_id": row["candidate_id"],
        "title": row["title"], "publisher": row["publisher"],
        "publication_date_from_latest_metadata": row["ordering_basis"]["published_date"],
        "latest_region_assignment": row["region"],
        "latest_retrieval_status": row["evidence_retrieval_status"],
        "publisher_text_retained": False,
        "latest_run_ai_assessment_notes": {
            "provenance": "AI-derived audit notes, not publisher quotes or independent verification",
            "metadata_assessment": row["classification_reason"],
            "detailed_assessment": row["significance_rationale"] or None,
        },
        "saved_metadata": saved_metadata,
    })
    manifest.append({
        "review_id": review_id, "article_id": row["candidate_id"],
        "title": row["title"], "publisher": row["publisher"],
        "inclusion_reason": inclusion_reason,
        "enriched": row["enriched"], "selected": row["selected"],
        "classification_decision": row["classification_decision"],
        "classification_relevance": row["classification_relevance"],
        "final_relevance": row["relevance"],
        "final_significance": row["editorial_significance"],
        "metadata_rank": row["metadata_rank"],
        "url": saved_metadata["url"] if saved_metadata else None,
    })

queue = json.loads((OUT / "queue_context.json").read_text(encoding="utf-8"))
context = []
for i, row in enumerate(queue["pages"], start=1):
    context.append({"id": f"Q{i:02}", **row,
                    "provenance": "Existing Notion stored AI summary/factual notes; raw publisher text is not retained"})
payload = {
    "review_date": "2026-10-19", "source_audit": str(AUDIT.relative_to(ROOT)),
    "evidence_limitation": (
        "Latest-run rejected/deferred articles have no retained snippets or publisher text. "
        "Retrieval status extracted proves retrieval happened, not that text is supplied now. "
        "Latest audit rationales and Notion factual points are AI-derived traces, not independent verification. "
        "Older exact-ID RSS metadata is explicitly labelled and usually repeats headlines. "
        "No new article collection, website fetching, or factual research is allowed."
    ),
    "additional_candidates": chosen, "existing_queue": context,
}
(OUT / "review_input.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
(OUT / "candidate_manifest.json").write_text(json.dumps({
    "audit": str(AUDIT.relative_to(ROOT)), "audit_sha256": hashlib.sha256(AUDIT.read_bytes()).hexdigest(),
    "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
    "input_audit_records": len(audit["candidates"]),
    "classified_positive_records": len(pool),
    "latest_enriched_not_selected": sum(row["enriched"] and not row["selected"] for row in pool),
    "reviewed_additional_candidates": len(chosen),
    "reviewed_enriched": sum(row["enriched"] for row in manifest),
    "reviewed_deferred": sum(not row["enriched"] for row in manifest),
    "existing_queue_records": len(context),
    "raw_publisher_text_available": 0,
    "older_exact_id_metadata_matches": sum(row["saved_metadata"] is not None for row in chosen),
    "production_thresholds_applied_to_review": False,
    "prior_numeric_scores_withheld_from_sol": True,
    "candidates": manifest,
}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"additional_candidates":len(chosen),"enriched":sum(row["enriched"] for row in manifest),
                  "deferred":sum(not row["enriched"] for row in manifest),"existing_queue":len(context),
                  "input_bytes":(OUT/"review_input.json").stat().st_size}))

"""Render the saved Sol review and verify protected local files; no API calls."""

import csv
import hashlib
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
packet = json.loads((OUT / "review_input.json").read_text(encoding="utf-8"))
review = json.loads((OUT / "review.json").read_text(encoding="utf-8"))
usage = json.loads((OUT / "usage.json").read_text(encoding="utf-8"))
manifest = json.loads((OUT / "candidate_manifest.json").read_text(encoding="utf-8"))
before = json.loads((OUT / "protected_before.json").read_text(encoding="utf-8"))
checks = {name: (ROOT / name).is_file() and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
          for name, digest in before.items()}
assert all(checks.values()), "Protected production/configuration/state file changed"
audit_path = ROOT / manifest["audit"]
assert hashlib.sha256(audit_path.read_bytes()).hexdigest() == manifest["audit_sha256"]
integrity = {"protected_files": len(checks), "all_unchanged": all(checks.values()),
             "audit_unchanged": True, "production_pipeline_modified": False,
             "production_prompts_or_settings_modified": False,
             "persistent_ingestion_state_modified": False,
             "article_collection_calls": 0, "publisher_fetches": 0,
             "notion_read_operations": 8, "notion_write_operations": 0,
             "review_endpoint": "POST https://api.openai.com/v1/chat/completions",
             "model_requests": usage["request_count"], "checks": checks}
(OUT / "integrity.json").write_text(json.dumps(integrity, indent=2)+"\n", encoding="utf-8")

items = {row["id"]: row for row in packet["additional_candidates"] + packet["existing_queue"]}
reviews = {row["id"]: row for row in review["additional_reviews"] + review["existing_queue_reviews"]}
prior = {row["review_id"]: row for row in manifest["candidates"]}
state = json.loads((ROOT / ".local_state/seen_articles.json").read_text(encoding="utf-8"))
sources = {row.get("notion_page_id"): row.get("source") for row in state.values()}
for row in packet["existing_queue"]:
    row["publisher"] = sources.get(row["notion_id"], "Not retained")


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def heading(text):
    return ["", "## " + text, ""]


def add_review(lines, item_id):
    item, result = items[item_id], reviews[item_id]
    lines += [f"### {item_id}: {item['title']}", "",
              f"Publisher: **{item.get('publisher', 'Not retained')}**. Region: **{result['region']}**. Recommendation: **{result['recommendation']}**.", "",
              result["reason"], "",
              f"Genuinely new development: **{result['genuinely_new_development']}**. {result['novelty_reason']}", "",
              f"Evidence sufficient for editor triage: **{result['evidence_sufficient_for_editor_review']}**. "
              f"Evidence sufficient for publication: **{'Yes' if result['evidence_sufficient_for_publication'] else 'No'}**. {result['evidence_reason']}", ""]
    if item_id.startswith("C"):
        lines += [f"Publication date reported in latest metadata: {item['publication_date_from_latest_metadata']}. "
                  f"Latest retrieval status: {item['latest_retrieval_status']}; publisher text retained: **No**.", "",
                  f"Prior classifier/final relevance/final significance: "
                  f"{prior[item_id]['classification_relevance']} / {prior[item_id]['final_relevance']} / {prior[item_id]['final_significance']}. "
                  "These numeric scores were withheld from Sol.", ""]
        if item["saved_metadata"]:
            lines += [f"Earlier exact-ID RSS metadata: `{item['saved_metadata']['file']}`. This is not a new collection or latest-run article extract.", ""]
    if item_id.startswith("Q"):
        lines += [f"Existing Notion item: [{item['title']}]({item['url']}).", ""]
    if result["verification_checks"]:
        lines.append("Editor checks:")
        lines.append("")
        lines += ["- " + check for check in result["verification_checks"]]
        lines.append("")


audit_relative = os.path.relpath(audit_path, OUT).replace("\\", "/")
lines = ["# SOMA MATER morning editorial rescue", "",
         "**Evaluation only. No production changes, new article collection, publisher fetches or Notion writes.**", "",
         f"Source: [latest ingestion audit]({audit_relative}), run `20261019T003107332472Z_488d8187`, "
         "plus saved run results and a read-only snapshot of the seven existing Article Queue items.", "",
         "**Result: two additional articles for editorial review; seven proposed morning review items in total. "
         "None is approved for publication on the retained evidence.**", ""]
lines += heading("Evidence limitations")
lines += ["The latest run fetched text for some rejected candidates, but did not persist that text or their RSS descriptions. "
          "Its retained fields are headlines, dates, classifications, retrieval statuses and AI-derived assessment rationales. "
          "A status of `extracted` is not supplied publisher text. Existing Notion Research Notes are AI-derived factual notes, not a retained independent source extract.", "",
          "The user confirmed that no separate latest-run evidence export is available. Exact-ID matches in older saved RSS snapshots "
          "were included only where available, labelled as earlier metadata; their descriptions generally repeat headlines. "
          "They were never presented as latest-run retrieved evidence.", "",
          "Both recommended additions have an `extracted` status in the latest audit, but their publisher text and publisher URLs "
          "were not retained in the available files. Locate them by their exact headlines during human verification. "
          "Their recommendations describe editorial fit for triage, not independently verified publication readiness.", ""]
lines += heading("Review scope and method")
lines += [f"The audit contains {manifest['input_audit_records']} evaluation records, including 158 Relevant/Borderline classifications "
          "and 47 enriched-but-unselected candidates. Manual evaluation sampling selected "
          f"**{manifest['reviewed_additional_candidates']} additional candidates: {manifest['reviewed_enriched']} enriched and "
          f"{manifest['reviewed_deferred']} deferred**, plus seven existing Queue items for duplicate/context review. "
          "The full 1,445-article feed pool was not sent to Sol.", "",
          "Sampling prioritized plausible new financing, infrastructure, policy and systemic climate/supply-chain findings, "
          "with a few applied-science, commentary and duplicate boundary cases. Routine weather, one-off distributions, "
          "generic oil-market reporting and other obvious non-mission material were excluded from the model packet. "
          "All 31 sampled items were present in the latest audit and classified Relevant or Borderline. "
          "See `candidate_manifest.json` for each inclusion reason and its original scores/rank.", "",
          "GPT-6 Sol independently assessed the source-only packet. Prior numeric scores were withheld. "
          "No production threshold, regional quota, publisher cap or 70/20/10 formula was used to decide editorial recommendations. "
          "This does not change those production settings. The one-off prompt and exact API request/response are saved alongside this report.", ""]
lines += heading("Ranked additional recommendations (maximum eight)")
lines += ["| Rank | Title | Publisher | Region | Recommendation | New development? | Evidence for triage / publication |",
          "|---:|---|---|---|---|---|---|"]
for rank, item_id in enumerate(review["ranked_additional_ids"], start=1):
    item, result = items[item_id], reviews[item_id]
    lines.append("| " + " | ".join(map(cell, (rank, item["title"], item["publisher"], result["region"],
                 result["recommendation"], result["genuinely_new_development"],
                 result["evidence_sufficient_for_editor_review"] + " / No"))) + " |")
lines += ["", "Only two additions were recommended; the list was not padded to eight.", ""]
for item_id in review["ranked_additional_ids"]:
    add_review(lines, item_id)

lines += heading("Proposed final morning Article Queue")
lines += ["This is a human-review proposal, not a Notion write list or publication approval. "
          "All seven items have **Partial** retained evidence and require source checks.", "",
          "| Order | Action | Title | Publisher | Region | Recommendation | New development? | Editorial angle / first check |",
          "|---:|---|---|---|---|---|---|---|"]
for rank, row in enumerate(review["recommended_morning_queue"], start=1):
    item, result = items[row["id"]], reviews[row["id"]]
    title = f"[{item['title']}]({item['url']})" if row["id"].startswith("Q") else item["title"]
    lines.append("| " + " | ".join(map(cell, (rank, row["action"], title, item["publisher"], result["region"],
                 result["recommendation"], result["genuinely_new_development"],
                 row["editorial_angle"] + " Check: " + "; ".join(row["verification_needed"])))) + " |")
lines += heading("Existing items to hold or reject")
for row in review["existing_queue_reviews"]:
    if row["recommendation"] == "Reject":
        lines += [f"- **{items[row['id']]['title']}**: {row['reason']} {row['novelty_reason']}"]
lines += ["", "No existing Notion item was removed, edited, reclassified or archived."]

lines += heading("Duplicate-event and related-story groups")
for group in review["duplicate_event_groups"]:
    lines += [f"### {group['group_id']}: {group['label']} — {group['relationship']}", "", group["reason"], ""]
    lines += ["- " + member + ": " + items[member]["title"] for member in group["member_ids"]]
    representative = group["representative_id"]
    lines += ["", "Best representative for context: " + (representative + " — " + items[representative]["title"] if representative else "None"), ""]
lines += ["The GERD record is a duplicate article, not a new dam event. Minerals and Gaza groups remain possible overlaps, "
          "not established identical announcements. Rail-access and West Bank reports concern related but distinct developments; "
          "a shared topic alone was not used to merge them.", ""]

lines += heading("API usage and cost")
prompt_total = sum(row["usage"]["prompt_tokens"] for row in usage["requests"] if row.get("usage"))
output_total = sum(row["usage"]["completion_tokens"] for row in usage["requests"] if row.get("usage"))
details = usage["requests"][0]["usage"]
lines += [f"- Requested and returned model: **gpt-6-sol**; reasoning effort medium; Standard/default service tier.",
          f"- Requests: **{usage['request_count']}**; structured-output validation passed; no repair request needed.",
          f"- Input: **{prompt_total:,} tokens**; output: **{output_total:,} tokens**; total **{prompt_total+output_total:,}**.",
          f"- Output includes **{details['completion_tokens_details']['reasoning_tokens']:,} reasoning tokens**; these are not charged twice.",
          f"- Reported cache-write input: **{details['prompt_tokens_details'].get('cache_write_tokens',0):,}**; cached reads: **{details['prompt_tokens_details'].get('cached_tokens',0):,}**.",
          f"- Estimated cost: **${usage['estimated_usd']:.6f}** (about **$0.122**); review request latency **{usage['latency_seconds']:.1f}s**.",
          "- Standard per-million rates: $2 uncached input, $0.20 cached input, $2.50 cache writes, $10 output. "
          "The estimate includes the reported cache-write rate. [Official model pricing](https://developers.openai.com/api/docs/models/gpt-6-sol).",
          "- Calculation: 3 uncached-input tokens × $2/M + 15,781 cache-write tokens × $2.50/M + 8,237 output tokens × $10/M = **$0.1218285**.",
          "- Budget: at most two requests, 16,000 completion tokens per request and $0.75 conservative estimated reservation. "
          "Actual account billing may differ; this is a usage-based estimate, not an invoice.",
          "- Existing Notion reads: one database query and seven block-list reads. Notion writes: **0**. Article collection/publisher fetches: **0**.", ""]
lines += heading("Integrity and reproducibility")
lines += [f"All **{len(checks)} protected local files** matched their pre-review SHA-256 hashes. "
          "This includes production code, prompts, configuration, scripts/tests/docs, `.env`, and persistent ingestion state. "
          "The latest source audit also matched its saved hash. No production or persistent-state file was changed.", "",
          "Saved artifacts: `candidate_manifest.json`, `review_input.json`, `queue_context.json`, `reviewer_prompt.txt`, "
          "`request_1.json`, `response_1.json`, `review.json`, `usage.json`, `integrity.json`, `article_reviews.csv` and the one-off preparation/review/render scripts. "
          "These are confined to `.preview/editorial_rescue/20261019_morning/`.", "",
          "Offline response validation passed six checks. Model output was checked for exactly one review per C/Q ID, "
          "unknown/repeated/missing IDs, at most eight additions/Queue entries, invalid actions, rejected items in the Queue, "
          "unsupported publication-readiness claims and confirmed duplicate events in the proposal. "
          "Full production tests were not rerun because production files were unchanged.", ""]
lines += heading("Complete additional candidate decisions")
for result in review["additional_reviews"]:
    if result["id"] not in review["ranked_additional_ids"]:
        add_review(lines, result["id"])
lines += heading("Complete existing Queue decisions")
for result in review["existing_queue_reviews"]:
    add_review(lines, result["id"])
(OUT / "report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")

fields = ["id", "scope", "title", "publisher", "region", "recommendation", "reason", "genuinely_new_development",
          "novelty_reason", "evidence_sufficient_for_editor_review", "evidence_sufficient_for_publication",
          "evidence_reason", "verification_checks", "additional_rank"]
with (OUT / "article_reviews.csv").open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for item_id, result in reviews.items():
        item = items[item_id]
        row = {key: result.get(key, "") for key in fields}
        row.update(title=item["title"], publisher=item.get("publisher"),
                   scope="Additional" if item_id.startswith("C") else "Existing Queue",
                   verification_checks="; ".join(result["verification_checks"]),
                   additional_rank=review["ranked_additional_ids"].index(item_id)+1 if item_id in review["ranked_additional_ids"] else "")
        writer.writerow(row)
print(json.dumps({"report":str(OUT/"report.md"),"reviewed_additions":31,"existing_items":7,
                  "recommended_additions":len(review['ranked_additional_ids']),
                  "proposed_morning_queue":len(review['recommended_morning_queue']),
                  "protected_files_unchanged":len(checks),"estimated_usd":usage['estimated_usd']}))

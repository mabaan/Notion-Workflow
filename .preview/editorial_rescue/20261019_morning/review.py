"""Bounded, isolated Sol editorial evaluation; only OpenAI chat POSTs allowed."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import httpx
from openai import OpenAI

from research_automation.config import load_settings

OUT = Path(__file__).resolve().parent
MODEL = "gpt-6-sol"
MAX_REQUESTS = 2
MAX_OUTPUT_TOKENS = 16000
USD_BUDGET = 0.75
PRICES = {"input": 2.0, "cached_input": 0.20, "cache_write": 2.50, "output": 10.0}
REGIONS = ["Global", "UAE", "KSA", "Egypt", "Out of Scope/Unclear"]
GRADES = ["Strong", "Acceptable", "Reject"]
ANSWERS = ["Yes", "No", "Unclear"]


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def string(enum=None):
    return {"type": "string", **({"enum": enum} if enum else {})}


def array(items):
    return {"type": "array", "items": items}


item_schema = obj({
    "id": string(), "recommendation": string(GRADES), "region": string(REGIONS),
    "reason": string(), "genuinely_new_development": string(ANSWERS),
    "novelty_reason": string(),
    "evidence_sufficient_for_editor_review": string(["Yes", "Partial", "No"]),
    "evidence_sufficient_for_publication": {"type": "boolean"},
    "evidence_reason": string(), "verification_checks": array(string()),
})
schema = obj({
    "additional_reviews": array(item_schema), "existing_queue_reviews": array(item_schema),
    "ranked_additional_ids": array(string()),
    "duplicate_event_groups": array(obj({
        "group_id": string(), "label": string(), "member_ids": array(string()),
        "relationship": string(["Same event", "Possible same event", "Related, distinct developments"]),
        "reason": string(), "representative_id": string(),
    })),
    "recommended_morning_queue": array(obj({
        "id": string(), "action": string(["Retain", "Add provisionally"]),
        "editorial_angle": string(), "verification_needed": array(string()),
    })),
    "overall_assessment": string(), "evidence_limitations": array(string()),
})


def validate(result, packet):
    candidate_ids = {row["id"] for row in packet["additional_candidates"]}
    queue_ids = {row["id"] for row in packet["existing_queue"]}
    expected = candidate_ids | queue_ids
    for key, ids in (("additional_reviews", candidate_ids), ("existing_queue_reviews", queue_ids)):
        actual = [row["id"] for row in result[key]]
        if len(actual) != len(set(actual)) or set(actual) != ids:
            raise ValueError("Missing, unknown or repeated review IDs")
    reviews = {row["id"]: row for row in result["additional_reviews"] + result["existing_queue_reviews"]}
    for row in reviews.values():
        if row["recommendation"] not in GRADES or row["region"] not in REGIONS:
            raise ValueError("Invalid grade/region")
        if row["genuinely_new_development"] not in ANSWERS:
            raise ValueError("Invalid novelty answer")
        if not isinstance(row["evidence_sufficient_for_publication"], bool):
            raise ValueError("Invalid publication-sufficiency answer")
        # This packet contains no independent publisher text to support approval.
        if row["evidence_sufficient_for_publication"]:
            raise ValueError("Unsupported publication-readiness claim")
        if len(row["verification_checks"]) > 3:
            raise ValueError("Too many verification checks")
    ranked = result["ranked_additional_ids"]
    if len(ranked) > 8 or len(ranked) != len(set(ranked)) or not set(ranked) <= candidate_ids:
        raise ValueError("Invalid additional shortlist")
    final_ids = [row["id"] for row in result["recommended_morning_queue"]]
    if len(final_ids) > 8 or len(final_ids) != len(set(final_ids)) or not set(final_ids) <= expected:
        raise ValueError("Invalid morning Queue")
    for item_id in set(ranked) | set(final_ids):
        if reviews[item_id]["recommendation"] == "Reject" or reviews[item_id]["evidence_sufficient_for_editor_review"] == "No":
            raise ValueError("Rejected/unsupported item in a shortlist")
    for row in result["recommended_morning_queue"]:
        if row["action"] != ("Retain" if row["id"] in queue_ids else "Add provisionally"):
            raise ValueError("Wrong Queue action")
        if row["id"] in candidate_ids and row["id"] not in ranked:
            raise ValueError("Morning addition missing from additional shortlist")
    for group in result["duplicate_event_groups"]:
        members = group["member_ids"]
        if len(members) < 2 or len(members) != len(set(members)) or not set(members) <= expected:
            raise ValueError("Invalid event group")
        if group["representative_id"] and group["representative_id"] not in members:
            raise ValueError("Invalid event representative")
        if group["relationship"] == "Same event":
            if len(set(members) & set(final_ids)) > 1:
                raise ValueError("Same event repeated in morning Queue")
            if set(members) & queue_ids and set(members) & set(ranked):
                raise ValueError("Already-represented event recommended as additional")


def self_test():
    # Focused offline validation, independent of article judgments or real calls.
    packet = {"additional_candidates": [{"id": "C01"}], "existing_queue": [{"id": "Q01"}]}
    def row(item_id):
        return {"id": item_id, "recommendation": "Acceptable", "region": "UAE",
                "genuinely_new_development": "Yes", "evidence_sufficient_for_publication": False,
                "evidence_sufficient_for_editor_review": "Partial", "verification_checks": []}
    good = {"additional_reviews": [row("C01")], "existing_queue_reviews": [row("Q01")],
            "ranked_additional_ids": ["C01"], "recommended_morning_queue": [], "duplicate_event_groups": []}
    validate(good, packet)
    changes = [lambda x: x["additional_reviews"].append(row("C01")),
               lambda x: x.update(additional_reviews=[]),
               lambda x: x.update(ranked_additional_ids=["unknown"]),
               lambda x: x.update(ranked_additional_ids=["C01"] * 9),
               lambda x: x["additional_reviews"][0].update(evidence_sufficient_for_publication=True)]
    for mutate in changes:
        bad = json.loads(json.dumps(good))
        mutate(bad)
        try:
            validate(bad, packet)
        except ValueError:
            continue
        raise AssertionError("Malformed response accepted")
    print("Offline reviewer validation: 6 checks passed; no API calls")


def main():
    packet = json.loads((OUT / "review_input.json").read_text(encoding="utf-8"))
    system = (OUT / "reviewer_prompt.txt").read_text(encoding="utf-8")
    payload = {"model": MODEL, "reasoning_effort": "medium", "service_tier": "default",
               "max_completion_tokens": MAX_OUTPUT_TOKENS,
               "response_format": {"type": "json_schema", "json_schema": {
                   "name": "morning_editorial_rescue", "strict": True, "schema": schema}},
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}]}
    # Byte count is a conservative token reservation, with message/schema overhead.
    input_bound = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024
    reserved_usd = (input_bound * PRICES["cache_write"] + MAX_OUTPUT_TOKENS * PRICES["output"]) / 1_000_000
    ledger = {"model": MODEL, "max_requests": MAX_REQUESTS, "max_output_tokens_per_request": MAX_OUTPUT_TOKENS,
              "estimated_usd_budget": USD_BUDGET, "pricing_per_million": PRICES,
              "pricing_source": "https://developers.openai.com/api/docs/models/gpt-6-sol",
              "requests": [], "estimated_usd": 0.0, "publisher_fetches": 0, "notion_writes": 0}
    if reserved_usd * MAX_REQUESTS > USD_BUDGET:
        raise ValueError("Review packet exceeds the conservative two-request reservation")
    settings = load_settings()
    def guard(request):
        if request.method != "POST" or request.url.host != "api.openai.com" or request.url.path != "/v1/chat/completions":
            raise RuntimeError("Only the editorial OpenAI chat endpoint is allowed")
    start = time.perf_counter()
    with httpx.Client(timeout=180, event_hooks={"request": [guard]}) as http_client:
        with OpenAI(api_key=settings.openai_api_key, http_client=http_client, max_retries=0) as api:
            for attempt in range(1, MAX_REQUESTS + 1):
                (OUT / f"request_{attempt}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                sent = time.perf_counter()
                entry = {"attempt": attempt, "reserved_usd": reserved_usd,
                         "started_at_utc": datetime.now(timezone.utc).isoformat()}
                ledger["requests"].append(entry)
                try:
                    response = api.chat.completions.create(**payload)
                except Exception as exc:
                    entry.update(status="api_error", error_category=type(exc).__name__, usage=None)
                    (OUT / "usage.json").write_text(json.dumps(ledger, indent=2)+"\n", encoding="utf-8")
                    # Avoid an unmetered automatic repeat of a timed-out request.
                    raise RuntimeError("Editorial request failed; saved sanitized usage ledger") from None
                raw = response.model_dump(mode="json")
                (OUT / f"response_{attempt}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                usage = response.usage.model_dump(mode="json") if response.usage else None
                entry.update(usage=usage, returned_model=response.model,
                             service_tier=getattr(response, "service_tier", None),
                             latency_seconds=round(time.perf_counter()-sent, 3))
                if usage:
                    prompt_tokens = usage["prompt_tokens"]
                    output_tokens = usage["completion_tokens"]
                    details = usage.get("prompt_tokens_details") or {}
                    cached = details.get("cached_tokens", 0) or 0
                    writes = details.get("cache_write_tokens", details.get("cache_creation_tokens", 0)) or 0
                    uncached = max(0, prompt_tokens-cached-writes)
                    entry["estimated_usd"] = (uncached*PRICES["input"] + cached*PRICES["cached_input"] + writes*PRICES["cache_write"] + output_tokens*PRICES["output"])/1_000_000
                    entry["cache_write_surcharge"] = "Only included when reported; account-specific billing may differ"
                    ledger["estimated_usd"] += entry["estimated_usd"]
                else:
                    entry["estimated_usd"] = None
                try:
                    if response.model != MODEL:
                        raise ValueError("Unexpected returned model")
                    if response.choices[0].finish_reason != "stop":
                        raise ValueError("Incomplete model output")
                    result = json.loads(response.choices[0].message.content)
                    validate(result, packet)
                except (ValueError, TypeError, KeyError) as exc:
                    entry.update(status="malformed_response", validation_error=str(exc))
                    (OUT / "usage.json").write_text(json.dumps(ledger, indent=2)+"\n", encoding="utf-8")
                    if attempt == MAX_REQUESTS or ledger["estimated_usd"] + reserved_usd > USD_BUDGET:
                        raise ValueError("Review did not pass bounded output validation") from None
                    # Same source-only packet and schema; no new articles or evidence.
                    continue
                entry["status"] = "validated"
                ledger["latency_seconds"] = round(time.perf_counter()-start, 3)
                ledger["request_count"] = len(ledger["requests"])
                (OUT / "review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                (OUT / "usage.json").write_text(json.dumps(ledger, indent=2)+"\n", encoding="utf-8")
                print(json.dumps({"model":response.model,"requests":len(ledger["requests"]),
                                  "estimated_usd":ledger["estimated_usd"],"usage":usage,
                                  "ranked_additions":result["ranked_additional_ids"],
                                  "morning_queue_count":len(result["recommended_morning_queue"])}))
                return


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        main()

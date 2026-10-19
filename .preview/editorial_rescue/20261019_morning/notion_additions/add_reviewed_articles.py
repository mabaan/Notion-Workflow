"""One-off, explicitly authorized editorial additions; no ingestion or LLM calls."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from research_automation.clients.notion_client import NotionClient
from research_automation.config import load_settings
from research_automation.notion_schema import ARTICLE_QUEUE as AQ
from research_automation.pipeline.deduplicate import SeenArticleStore
from research_automation.utils import notion_properties as props
from research_automation.utils.hashing import build_content_hash, build_url_hash
from research_automation.utils.urls import clean_url


OUT = Path(__file__).resolve().parent
REVIEW = OUT.parent
ROOT = REVIEW.parents[2]
SOURCE_ID = "3cec995b-3347-81be-9871-db9c2830ac5a"
DATASET_ID = "3fdc995b-3347-81ce-853b-e50347c6946b"
SPECS = {
    "C03": {
        "url": "https://www.theguardian.com/environment/2026/oct/16/brazil-amazon-deforestation-lowest-on-record-election",
        "published": "2026-10-16T18:56:00+00:00",
        "summary": "Brazil reports a 41.8% annual fall in Amazon deforestation to a record low.",
        "topics": ["Climate", "Environment", "net zero transition"],
        "editor_check": "Check the primary monitoring release and measurement window before publication; distinguish measured results from election scenarios.",
    },
    "C04": {
        "url": "https://www.theguardian.com/environment/2026/oct/16/vw-ford-tesla-batteries-deforestation-indigenous-lands",
        "published": "2026-10-16T07:00:00+00:00",
        "summary": "An investigation links EV battery supply chains to deforestation; connections to individual batteries remain unconfirmed.",
        "topics": ["energy transition", "supply chains", "Environment"],
        "editor_check": "Review the investigation's tracing method and company responses. Supply-chain associations must not be presented as confirmed links to individual batteries.",
    },
}


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def text_value(page, name):
    value = page.get("properties", {}).get(name, {})
    return "".join(i.get("plain_text", i.get("text", {}).get("content", "")) for i in value.get("title", value.get("rich_text", [])))


def block(value, kind="paragraph"):
    return {"object": "block", "type": kind, kind: {"rich_text": props.rich_text_items(value)}}


def fingerprints():
    paths = [ROOT / ".env", ROOT / ".env.example", ROOT / "README.md"]
    for folder in ("src", "scripts", "tests", "docs"):
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.exists()}


def matching_page(pages, item):
    expected_url = clean_url(item["url"])
    expected_title = " ".join(item["title"].casefold().split())
    matches = []
    for page in pages:
        values = page.get("properties", {})
        urls = [clean_url(values.get(AQ[key], {}).get("url") or "") for key in ("url", "canonical_url")]
        title = " ".join(text_value(page, AQ["title"]).casefold().split())
        if expected_url in urls or title == expected_title or text_value(page, AQ["url_hash"]) in {item["url_hash"], item["article_id"]}:
            matches.append(page)
    if len(matches) > 1:
        raise RuntimeError("Multiple existing pages match; no further writes performed.")
    return matches[0] if matches else None


def main():
    write = "--write" in sys.argv
    settings = load_settings()
    notion = NotionClient(settings.notion_token)
    database_id = settings.notion_article_queue_database_id
    database = notion.retrieve_database(database_id)
    schema = database["properties"]
    notion.retrieve_page(SOURCE_ID)
    dataset = notion.retrieve_page(DATASET_ID)
    assert not dataset.get("archived")
    assert "October" in text_value(dataset, "Name")
    reviews = {i["id"]: i for i in json.loads((REVIEW / "review.json").read_text(encoding="utf-8"))["additional_reviews"]}
    manifest = {i["review_id"]: i for i in json.loads((REVIEW / "candidate_manifest.json").read_text(encoding="utf-8"))["candidates"]}
    proposal = {i["id"]: i for i in json.loads((REVIEW / "morning_queue_proposal.json").read_text(encoding="utf-8"))["items"]}
    pages_before = notion.query_database(database_id)
    before = fingerprints()
    now = datetime.now(timezone.utc).isoformat()
    planned = []
    for review_id, spec in SPECS.items():
        review, old, proposed = reviews[review_id], manifest[review_id], proposal[review_id]
        assert review["recommendation"] in {"Strong", "Acceptable"}
        item = dict(spec, review_id=review_id, title=old["title"], article_id=old["article_id"], url_hash=build_url_hash(clean_url(spec["url"])))
        assert set(spec["topics"]) <= {i["name"] for i in schema[AQ["topic"]]["multi_select"]["options"]}
        properties = {
            AQ["title"]: props.title(item["title"]),
            AQ["url"]: props.url(item["url"]),
            AQ["canonical_url"]: props.url(clean_url(item["url"])),
            AQ["source"]: props.relation([SOURCE_ID]),
            AQ["dataset_meeting"]: props.relation([DATASET_ID]),
            AQ["published_date"]: props.date_value(spec["published"]),
            AQ["collected_date"]: props.date_value(now),
            AQ["region"]: props.multi_select([review["region"]]),
            AQ["topic"]: props.multi_select(spec["topics"]),
            AQ["summary"]: props.rich_text(spec["summary"]),
            AQ["why_it_matters"]: props.rich_text(review["reason"]),
            AQ["newsletter_angle"]: props.rich_text(proposed["editorial_angle"]),
            AQ["relevance_score"]: props.number(old["final_relevance"]),
            AQ["status"]: props.select("New"),
            AQ["processed"]: props.checkbox(True),
            AQ["last_processed"]: props.date_value(now),
            AQ["duplicate"]: props.checkbox(False),
            AQ["url_hash"]: props.rich_text(item["url_hash"]),
            AQ["content_hash"]: props.rich_text(build_content_hash(item["title"], old["publisher"])),
            AQ["error_notes"]: props.rich_text(""),
        }
        assert set(properties) <= set(schema)
        children = [
            block("Editorial rescue review", "heading_2"),
            block(f"Editorial recommendation: {review['recommendation']}. Region: {review['region']}. Status: New; awaiting human editorial approval."),
            block(review["reason"]),
            block("New development: " + review["genuinely_new_development"] + ". " + review["novelty_reason"]),
            block("Evidence and verification", "heading_2"),
            block("Publisher link and publication date checked on 19 October 2026. The prior Sol review used saved metadata and audit notes; this addition does not represent a new full-text Sol assessment."),
            block("Human verification before publication: " + spec["editor_check"]),
            block("Source: " + item["url"]),
            block("Scoring provenance", "heading_2"),
            block(f"Original classifier relevance: {old['classification_relevance']}/5 ({old['classification_decision']}); original detailed relevance: {old['final_relevance']}/5; original editorial significance: {old['final_significance']}/5. The numeric Relevance Score retains the original value. Sol's independent editorial recommendation is recorded separately above."),
            block("User-authorized manual editorial addition following the GPT-6 Sol rescue review. This is an editorial exception to automated selection and publisher caps, not a strict/fallback pipeline winner. Production rules and budgets are unchanged."),
            block(f"Review ID: {review_id}; original article ID: {old['article_id']}. Local review: .preview/editorial_rescue/20261019_morning/review.json; source audit: 20261019T003107332472Z_488d8187.json."),
        ]
        existing = matching_page(pages_before, item)
        planned.append(dict(item, properties=properties, children=children, existing_page_id=existing["id"] if existing else None))
    save("plan.json", {"write_requested": write, "queue_before": len(pages_before), "items": planned})
    if not write:
        print(json.dumps({"planned": [{"id": i["review_id"], "title": i["title"], "existing_page_id": i["existing_page_id"]} for i in planned], "queue_before": len(pages_before)}, ensure_ascii=False))
        return
    save("protected_before.json", before)
    save("queue_before.json", pages_before)
    store = SeenArticleStore(settings.seen_articles_path)
    save("seen_before.json", store.records)
    receipts = []
    for item in planned:
        current = notion.query_database(database_id)
        page = matching_page(current, item)
        created = page is None
        if created:
            try:
                page = notion.create_page(database_id, item["properties"], item["children"])
            except Exception:
                # Resolve ambiguous create outcomes by reading, never blindly retrying.
                page = matching_page(notion.query_database(database_id), item)
                if page is None:
                    raise
        receipt = {"review_id": item["review_id"], "title": item["title"], "page_id": page["id"], "url": page.get("url"), "created": created}
        receipts.append(receipt)
        save("receipts.json", receipts)
        verified = notion.retrieve_page(page["id"])
        assert text_value(verified, AQ["title"]) == item["title"]
        assert verified["properties"][AQ["status"]]["select"]["name"] == "New"
        assert verified["properties"][AQ["canonical_url"]]["url"] == clean_url(item["url"])
        assert DATASET_ID in {r["id"] for r in verified["properties"][AQ["dataset_meeting"]]["relation"]}
        assert SOURCE_ID in {r["id"] for r in verified["properties"][AQ["source"]]["relation"]}
        assert verified["properties"][AQ["region"]]["multi_select"][0]["name"] == "Global"
        blocks = notion.list_block_children(page["id"])
        assert len(blocks) >= len(item["children"])
        save(item["review_id"] + "_verified.json", {"page": verified, "blocks": blocks})
        for identity in {item["url_hash"], item["article_id"]}:
            store.record(url_hash=identity, title=item["title"], canonical_url=clean_url(item["url"]), source="The Guardian International", notion_page_id=page["id"], created_at=page["created_time"])
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
    after_pages = notion.query_database(database_id)
    save("queue_after.json", after_pages)
    after_by_id = {p["id"]: p for p in after_pages}
    assert all(p["properties"] == after_by_id[p["id"]]["properties"] for p in pages_before)
    assert before == fingerprints(), "Production/configuration file changed during manual additions."
    result = {"added": sum(r["created"] for r in receipts), "queue_before": len(pages_before), "queue_after": len(after_pages), "notion_items": receipts, "existing_queue_properties_unchanged": True, "production_configuration_files_unchanged": True, "llm_requests": 0, "llm_cost_usd": 0, "source": "Existing GPT-6 Sol editorial rescue review; publisher links verified", "local_seen_records": len(store.records)}
    save("result.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

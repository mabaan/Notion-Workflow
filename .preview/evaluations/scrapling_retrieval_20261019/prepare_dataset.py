"""Freeze known candidate URLs from saved metadata; no network or live clients."""
from pathlib import Path
from collections import Counter, defaultdict, deque
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AUDIT = ROOT / ".preview/ingestion_audits/20261019T131713503320Z_0b40c7fc.json"
audit = json.loads(AUDIT.read_text(encoding="utf-8"))["candidates"]
files = [ROOT / ".preview/evaluations/luna_followup_2026-10-19" / name
         for name in ("collected_metadata.json", "targeted_metadata.json", "egypt_metadata.json")]
metadata = []
for path in files:
    value = json.loads(path.read_text(encoding="utf-8"))
    for row in value if isinstance(value, list) else value.get("articles", []):
        metadata.append(dict(row, saved_file=str(path.relative_to(ROOT))))
by_id = {row["article_id"]: row for row in metadata}

def normalized(title):
    return re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()

by_title = {normalized(row["title"]): row for row in metadata}

# Exact headline lookups, not a new discovery pool. Search results/primary source
# links were inspected. No alternative publisher is substituted for missing URLs.
recoveries = {
    "Global conservation area coverage substantially exceeds current estimates - Nature": (
        "https://www.nature.com/articles/s41586-026-11157-4", "Nature primary article search result"),
    "Global food inflation is expected to intensify as supply shocks pile up - Reuters": (
        "https://www.reuters.com/world/americas/global-food-inflation-is-expected-intensify-supply-shocks-pile-up-2026-10-19/", "Exact Reuters reference URL in Economic impact of the 2026 Iran war; source page unavailable during lookup"),
    "No 10 leaves option open to impose Chinese EV tariffs if UK joins EU scheme": (
        "https://www.theguardian.com/politics/2026/oct/16/uk-chinese-electric-vehicle-ev-tariffs-eu-made-in-europe-scheme", "Guardian exact-title search result; latest successful-retrieval control"),
    "UAE delegation explores energy and transport partnerships in China - Dubai Eye 103.8 - News, Talk & Sports": (
        "https://www.dubaieye1038.com/news/business/uae-delegation-explores-energy-and-transport-partnerships-in-china/", "Dubai Eye exact-title search result; latest successful-retrieval control"),
    "How waste-to-energy projects in the UAE are advancing food security and unlocking value": (
        "https://farrellymitchell.com/clean-energy-consulting/waste-to-energy-projects-uae/", "Farrelly Mitchell exact-title search result; latest successful-retrieval control"),
}


def record(row):
    source = by_id.get(row["candidate_id"])
    basis = "saved metadata exact input-ID match"
    if source is None:
        source = by_title.get(normalized(row["title"]))
        basis = "saved metadata normalized-title match; input URL may differ from latest run"
    recovered = recoveries.get(row["title"])
    if source:
        url, provenance = source["url"], source["saved_file"] + "; " + basis
    elif recovered:
        url, provenance = recovered
    else:
        return None
    return dict(article_id=row["candidate_id"], title=row["title"], publisher=row["publisher"],
                url=url, url_provenance=provenance, snippet=source.get("snippet", "") if source else "",
                original_retrieval_status=row["evidence_retrieval_status"], selected=row["selected"],
                enriched=row["enriched"], classification=row.get("classification_decision"),
                final_reason=row["reason"], publication_date=row["ordering_basis"]["published_date"],
                stratum="selected" if row["selected"] else "successful_control" if row["evidence_retrieval_status"] == "extracted" else "enriched_weak_evidence" if row["enriched"] else "classified_metadata_supplement")


chosen, used, unavailable = [], set(), []
# Controls first make a useful early smoke check, without separate duplicate calls.
priority = sorted([r for r in audit if r["enriched"]], key=lambda r: (
    r["evidence_retrieval_status"] != "extracted", not r["selected"],
    r.get("relevance") or 0, r["candidate_id"],
))
for row in priority:
    item = record(row)
    if item and item["url"] not in used:
        chosen.append(item)
        used.add(item["url"])
    elif row["selected"] and item is None:
        unavailable.append(dict(article_id=row["candidate_id"], title=row["title"], publisher=row["publisher"],
                                url=None, reason="Audit has no URL; no saved metadata match. Original publisher URL could not be recovered without guessing; no substitute publisher used."))

# Publisher round-robin fills the bounded sample from the same latest classified
# pool, using existing captured inputs only. No live RSS collection or search.
pools = defaultdict(deque)
for row in audit:
    if row["classification_decision"] in {"Relevant", "Borderline"} and not row["enriched"]:
        item = record(row)
        if item and item["url"] not in used:
            pools[item["publisher"]].append(item)
while len(chosen) < 40 and any(pools.values()):
    for publisher in sorted(pools):
        if pools[publisher] and len(chosen) < 40:
            item = pools[publisher].popleft()
            if item["url"] not in used:
                chosen.append(item)
                used.add(item["url"])

dataset = dict(source_audit=str(AUDIT.relative_to(ROOT)), audit_sha256=hashlib.sha256(AUDIT.read_bytes()).hexdigest(),
               articles=chosen, unavailable_selected=unavailable,
               selected_total=sum(r["selected"] for r in audit),
               selected_with_url=sum(r["selected"] for r in chosen),
               url_count=len(chosen), strata=dict(Counter(r["stratum"] for r in chosen)),
               publishers=dict(Counter(r["publisher"] for r in chosen)),
               caveat="Same frozen URL/title/snippet per method. Recovered publisher URLs differ from historical Google-wrapper inputs; changes versus historical audit are not attributed to Scrapling. Missing descriptions remain empty. Supplemental cases were classified, not enriched, in the latest run.")
(OUT / "dataset.json").write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k:v for k,v in dataset.items() if k != "articles"}, indent=2, ensure_ascii=False))

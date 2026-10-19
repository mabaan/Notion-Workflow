"""Two predeclared same-story direct-URL diagnostics, without new discovery."""
from pathlib import Path
import json

OUT = Path(__file__).resolve().parent
primary = json.loads((OUT / "dataset.json").read_text(encoding="utf-8"))
pairs = {
    "IMF cuts 2026 growth forecasts for Gulf economies due to prolonged Hormuz closure - The National":
        "https://www.thenationalnews.com/business/economy/2026/10/13/imf-cuts-2026-growth-forecasts-for-gulf-economies-due-to-prolonged-hormuz-closure/",
    "Greenland takes a step toward banning deep-sea mining - Arab News":
        "https://www.arabnews.com/world/greenland-takes-a-step-toward-banning-deep-sea-mining-3006601",
}
items = []
for title, url in pairs.items():
    original = next(row for row in primary["articles"] if row["title"] == title)
    items.append(dict(original, url=url, original_wrapper_url=original["url"],
                      stratum="publisher_url_diagnostic", case_id=original["article_id"] + ":publisher-url",
                      url_provenance="Exact-headline primary publisher search result, fixed before direct-URL benchmark; same article, not a new discovery"))
dataset = dict(source_audit=primary["source_audit"], articles=items,
               caveat="Secondary same-story URL-resolution diagnostic, reported separately. A gain versus the wrapper is not a Scrapling extraction gain.")
(OUT / "publisher_url_pairs.json").write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
combined = dict(primary, articles=primary["articles"] + items, url_count=42, distinct_articles=40,
                caveat=primary["caveat"] + " Two secondary publisher-URL cases repeat known stories for URL-resolution sensitivity; 42 URLs cover 40 distinct articles.")
(OUT / "dataset_complete.json").write_text(json.dumps(combined, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Prepared two direct publisher URL diagnostics; combined benchmark 42 URLs / 40 distinct articles.")

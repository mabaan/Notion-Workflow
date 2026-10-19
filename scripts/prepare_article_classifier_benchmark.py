"""Rebuild the frozen October convenience sample from saved files; no network.

Reference judgments are provisional analyst labels, not old model outputs. Changing
them after a live run creates a different benchmark and invalidates blind scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

import feedparser

from research_automation.pipeline.clean import clean_snippet, clean_text
from research_automation.sources.rss import _entry_datetime

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "tests/fixtures/article_classifier_benchmark.json"


def prepare() -> dict:
    rows = []

    def add(key, title, snippet, publisher, date, hints, quality, registered, url,
            stratum, provenance, decision, regions, rationale):
        rows.append(dict(
            article_id=key, title=title, snippet=snippet, publisher=publisher,
            published_date=date, source_region_hints=hints, source_quality=quality,
            registered=registered, url=url, stratum=stratum, provenance=provenance,
            reference=dict(decision=decision, acceptable_regions=regions, rationale=rationale),
        ))

    feed_path = "tests/fixtures/agbi_feed_sample_2026-10-15.xml"
    feed = feedparser.parse((ROOT / feed_path).read_bytes())
    rss_reference = [
        ("Irrelevant", [], "Petroleum trade/banking resumption; no supported food, water or transition consequence."),
        ("Borderline", ["Out of Scope/Unclear"], "Concrete renewables/export proposal abroad with a Saudi company; credible commercial MENA bridge but foreign project, not KSA geography."),
        ("Borderline", ["Global"], "Major LNG operational disruption in MENA; indirect transition/security consequences unspecified."),
        ("Irrelevant", [], "Generic industrial IPO investment; no explicit mission application."),
        ("Irrelevant", [], "Semiconductor investment without a demonstrated mission application."),
        ("Borderline", ["Global"], "Regional logistics support could cover mission supply chains, but sectors unspecified; preserve uncertainty."),
        ("Irrelevant", [], "Oil-fleet sanctions/prices without a demonstrated mission consequence."),
        ("Irrelevant", [], "Hydrocarbon export commentary without a supported mission development."),
        ("Irrelevant", [], "Broad contracts/spending update; energy alone does not establish transition relevance."),
        ("Borderline", ["Global"], "Material Hormuz disruption, but cargo/agricultural effects unspecified; potential indirect mission bridge."),
    ]
    assert len(feed.entries) == len(rss_reference)
    for i, (entry, reference) in enumerate(zip(feed.entries, rss_reference)):
        add(f"rss-{i:02}", clean_text(entry.title), clean_snippet(entry.get("summary", "")),
            "AGBI", _entry_datetime(entry).isoformat(), ["GCC", "MENA"], 10, True,
            entry.link, "primary", dict(metadata=feed_path, snippet="saved RSS description only; content:encoded excluded",
                                       source_hints_quality="same publisher metadata from oct16_corrections.json (iraq)"), *reference)

    reference16 = {
        "negation": ("Irrelevant", [], "Trust commentary expressly disclaims energy/water; incidental keywords."),
        "battery_definition": ("Irrelevant", [], "Battery definition commentary; no demonstrated practical mission application."),
        "battery_science": ("Borderline", ["Out of Scope/Unclear", "Global"], "Plausible storage application but no demonstrated deployment; not high relevance."),
        "crypto": ("Irrelevant", [], "Crypto trading license without a mission consequence."),
        "flights": ("Irrelevant", [], "Passenger cancellations without a mission consequence."),
        "commission": ("Borderline", ["Out of Scope/Unclear", "KSA"], "Irrigation awards in France; possible Saudi application but operational consequences unknown. Not a new Saudi project."),
        "veal": ("Relevant", ["Egypt"], "New national livestock funding directly supports Egyptian agricultural capacity."),
        "gerd": ("Borderline", ["Global", "Egypt"], "Central Nile water-security topic, but explainer novelty and event geography unresolved."),
        "harvests": ("Relevant", ["Global"], "Explicit shipping-to-harvest production consequence; systemic food security."),
        "iraq": ("Relevant", ["Global"], "Solar expansion talks in Iraq; Saudi nationality is not project geography."),
        "libya": ("Borderline", ["Global"], "Consequential regional flooding; mission infrastructure/food effects unspecified."),
        "qatar": ("Relevant", ["Global"], "Potential material renewable share change in other MENA; assess forecast versus funded commitment later."),
    }
    path16 = "tests/fixtures/oct16_corrections.json"
    for row in json.loads((ROOT / path16).read_text(encoding="utf-8"))["candidates"]:
        if row["key"] == "self_newsletter":
            continue
        date = row["published"]
        if not date.endswith("+00:00"):
            date += "+00:00"
        add("oct16-" + row["key"], row["title"], "", row["publisher"], date,
            row["source_regions"], row["quality"], row["registered"], row["url"], "primary",
            dict(metadata=path16, snippet="unavailable; headline repetitions/synthetic descriptions omitted",
                 url="retained fixture placeholder; not a collected URL", date="original naive timestamps interpreted as UTC where applicable"),
            *reference16[row["key"]])

    reference15 = {
        "istanbul": ("Irrelevant", [], "School closures in Turkey without a demonstrated mission infrastructure or food effect."),
        "hormuz": ("Relevant", ["Global"], "Fertilizer-plan failure explicitly threatens food availability; distinct from observed harvest losses."),
        "bahrain": ("Borderline", ["Out of Scope/Unclear", "Global"], "MENA grid investment abroad could enable transition, but technology/purpose absent. Not a Bahrain project."),
    }
    path15 = "tests/fixtures/candidate_selection.json"
    for row in json.loads((ROOT / path15).read_text(encoding="utf-8"))["regressions"]:
        if row["key"] not in reference15:
            continue
        add("oct15-" + row["key"], row["title"], "", row["publisher"], row["published"],
            row["regions"], row["quality"], True, "https://fixture.example/oct15-" + row["key"],
            "primary", dict(metadata=path15, snippet="not an original collected description; omitted",
                            url="evaluation-only placeholder"), *reference15[row["key"]])

    # Only title/source/URL; never reuse stored enrichment, scores or Notion IDs.
    store = json.loads((ROOT / ".local_state/seen_articles.json").read_text(encoding="utf-8"))
    entries = store.get("articles", store) if isinstance(store, dict) else store
    if isinstance(entries, dict):
        entries = entries.values()
    for row in entries:
        if row["title"].startswith("410,000"):
            key, regions, reason = "saved-sharjah", ["UAE"], "Explicit large water/waste capacity and investment in Sharjah."
        elif row["title"].startswith("Egypt to get"):
            key, regions, reason = "saved-egypt-battery", ["Egypt"], "Practical lithium-ion assembly capacity development in Egypt."
        else:
            continue
        add(key, row["title"], "", row["source"], None, [], None, False, row["canonical_url"],
            "supplemental", dict(metadata=".local_state/seen_articles.json title/source/url only",
                                 snippet="unavailable", date="unavailable; created_at is not publication date"),
            "Relevant", regions, reason)
    add("user-west-bank", "'He irrigated the tree with his blood': West Bank olive farmers set for another deadly harvest",
        "", "The National", None, [], None, False, "", "supplemental",
        dict(metadata="actual headline supplied by user", snippet="unavailable", date="unavailable"),
        "Borderline", ["Global"], "Violence against farmers is not proof of food-system disruption; sparse title merits caution, never high relevance from agriculture alone.")

    # Exact scenario phrases from the user, NOT invented collected headlines.
    diagnostics = [
        ("uae-strategy", "UAE food-production strategy", "Relevant", ["UAE"], "Potential direct strategic food-capacity relevance; novelty/importance unresolved."),
        ("egypt-green", "Egypt green industrialisation, subject to novelty and evidence", "Borderline", ["Egypt"], "Potential industrial transition relevance; no specific new development supplied."),
        ("saudi-weather", "Routine Saudi weather forecasts", "Irrelevant", [], "Ordinary forecast with no demonstrated mission consequence."),
        ("landscape", "Agricultural landscape descriptions", "Irrelevant", [], "Scenery without a mission development."),
        ("economy", "Generic economic news mentioning energy", "Irrelevant", [], "Energy keyword alone is insufficient."),
        ("water-science", "Water-related laboratory papers without a demonstrated mission application", "Borderline", ["Out of Scope/Unclear", "Global"], "Not high relevance; potential application cannot be assessed from this generic description."),
        ("foreign-water", "Foreign-local water infrastructure projects without a MENA or systemic bridge", "Irrelevant", [], "Explicitly foreign-local without a regional/systemic link."),
    ]
    for key, title, decision, regions, rationale in diagnostics:
        add("diagnostic-" + key, title, "", "", None, [], None, False, "", "diagnostic",
            dict(metadata="user-described scenario, NOT a collected headline", snippet="not supplied", date="not supplied"),
            decision, regions, rationale)
    return dict(
        version=1, historical_as_of="2026-10-16T23:59:59+00:00",
        reference_status="Provisional analyst labels authored before model calls; not independently human adjudicated. Borderline excluded from binary precision/recall. Prior LLM scores/decisions not used.",
        limitations=["Small convenience sample, not population precision/recall.",
                     "Only ten original RSS descriptions available; other snippets empty.",
                     "Placeholder fixture URLs test editorial screening, not real URL validity.",
                     "Missing-date supplements bypass preparation only for diagnostics.",
                     "User scenarios excluded from collected-pool metrics.",
                     "No current seen-article exclusions applied in historical replay."],
        articles=rows,
    )


if __name__ == "__main__":
    snapshot = prepare()
    DESTINATION.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Frozen {len(snapshot['articles'])} metadata/reference records at {DESTINATION}")

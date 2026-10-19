from copy import deepcopy
from hashlib import sha256

import httpx
import pytest

from scripts.evaluate_article_classifier import FIXTURE
from scripts.evaluate_luna_followup import LIMITS, compare_runs, preflight, read


def result(key, decision, *, region="Global", score=3):
    return dict(article_id=key, classification=dict(
        decision=decision, assigned_region=region, relevance_score=score,
        primary_mission_topic="Water Security"))


def test_repeat_comparison_uses_ids_not_result_position_and_separates_retention():
    left = dict(outcomes=[result("a", "Borderline"), result("b", "Relevant")])
    right = dict(outcomes=[result("b", "Borderline", score=2), result("a", "Irrelevant", region="UAE")])
    compared = compare_runs(left, right)
    assert compared["jointly_classified"] == 2
    assert compared["changed"]["decision"] == ["a", "b"]
    assert compared["changed"]["retention"] == ["a"]
    assert compared["changed"]["assigned_region"] == ["a"]
    assert compared["changed"]["relevance_score"] == ["b"]


def test_preflight_reserves_every_stage_without_any_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Preflight must not send network requests")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    history = read(FIXTURE)
    rows = []
    for index in range(100):
        row = deepcopy(history["articles"][index % len(history["articles"])])
        row["article_id"] = sha256(str(index).encode()).hexdigest()
        rows.append(row)
    snapshot = dict(articles=rows, enrichment_panel_ids=[row["article_id"] for row in rows[:20]])
    frozen = deepcopy(snapshot)
    estimate = preflight(snapshot, history)
    assert snapshot == frozen
    assert estimate["planned_requests"] == 29  # 2x100 + 2x50 + 35, 20 paired, 4 Veal.
    assert 0 < estimate["reserved_tokens"] <= LIMITS["max_reserved_tokens"]
    assert 0 < estimate["reserved_usd"] <= LIMITS["max_reserved_usd"]


def test_full_batch_preflight_rejects_padded_or_incomplete_sample():
    history = read(FIXTURE)
    with pytest.raises(ValueError, match="100 distinct"):
        preflight(dict(articles=history["articles"], enrichment_panel_ids=[]), history)

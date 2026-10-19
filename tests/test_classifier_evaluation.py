"""The evaluation harness is offline unless explicitly run with --live."""
import json

import httpx
from openai import OpenAI
import pytest

from scripts.evaluate_article_classifier import (
    BudgetTransport, FIXTURE, baseline, experiment_plan, metric, model_input, summarize,
)
from research_automation.clients.article_classifier import ArticleClassifier
from research_automation.config import Settings


@pytest.fixture
def snapshot():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_snapshot_keeps_missing_metadata_and_reference_separate(snapshot):
    rows = snapshot["articles"]
    assert len(rows) == 35
    assert sum(row["stratum"] == "primary" for row in rows) == 25
    assert sum(bool(row["snippet"]) for row in rows) == 10
    assert len({row["article_id"] for row in rows}) == len(rows)
    for row in rows:
        record = model_input(row).as_record()
        assert "reference" not in record and "stratum" not in record
        assert "provenance" not in record and "source_quality" not in record
        if row["stratum"] != "primary":
            assert record["published_date"] is None
            assert record["snippet"] == ""


def test_baseline_is_order_independent_and_never_enriches(snapshot):
    original = json.loads(json.dumps(snapshot))
    left = baseline(snapshot)
    right = baseline({**snapshot, "articles": list(reversed(snapshot["articles"]))})
    assert left["rows"] == right["rows"]
    assert snapshot == original
    assert all(r["objective_eligible"] for key, r in left["rows"].items()
               if next(row for row in snapshot["articles"] if row["article_id"] == key)["stratum"] == "primary")
    assert not left["rows"]["saved-sharjah"]["objective_eligible"]
    assert left["rows"]["oct16-veal"]["retained"]


def test_metric_excludes_borderlines_and_reports_fail_open_uncertainty():
    rows = [dict(article_id=key, reference=dict(decision=label, acceptable_regions=["Global"]))
            for key, label in (("p", "Relevant"), ("n", "Irrelevant"), ("b", "Borderline"))]
    result = metric(rows, dict(p=True, n=True, b=False), dict(p="Global", n="UAE", b="Global"), ["p"])
    assert result["precision"] == 0.5
    assert result["recall"] == 1
    assert result["classified_positive_coverage"] == 0
    assert result["false_positives"] == ["n"]
    assert result["borderline_retained"] == 0
    assert result["wrong_regions"] == ["n"]


def test_unknown_date_supplements_are_not_legacy_editorial_false_negatives(snapshot):
    result = summarize(snapshot, baseline(snapshot), {})
    assert "deterministic" not in result["supplemental"]
    assert "deterministic" not in result["diagnostic"]
    assert result["supplemental"]["objective_exclusions"]["saved-sharjah"]


def test_null_date_serialization_and_local_budget_stops_all_model_requests(tmp_path, snapshot):
    sent = []
    delegate = httpx.MockTransport(lambda request: sent.append(request))
    transport = BudgetTransport(tmp_path, delegate=delegate,
                                limits=dict(max_requests=0, max_reserved_tokens=160000, max_reserved_usd=0.25))
    with OpenAI(api_key="offline-key", http_client=httpx.Client(transport=transport)) as client:
        report = ArticleClassifier(Settings(), client=client).classify([model_input(snapshot["articles"][-1])])
    assert not sent
    assert report.failed_ids and report.outcomes[0].eligible_for_assessment
    assert report.requests_without_usage == 1
    assert transport.ledger == []
    assert transport.denied == 1


def test_reservations_include_failed_requests_and_no_usage_is_not_zero_cost(tmp_path, snapshot):
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(503, json={"error": {"message": "offline", "type": "server_error"}})

    transport = BudgetTransport(tmp_path, delegate=httpx.MockTransport(respond),
                                limits=dict(max_requests=1, max_reserved_tokens=160000, max_reserved_usd=0.25))
    with OpenAI(api_key="offline-key", http_client=httpx.Client(transport=transport)) as client:
        report = ArticleClassifier(Settings(), client=client, sleep=lambda _: None).classify(
            [model_input(snapshot["articles"][0])])
    ledger = json.loads((tmp_path / "network_ledger.json").read_text())
    assert len(sent) == 1 and len(report.requests) == 2
    assert ledger["denied_locally"] == 1
    assert ledger["reserved_tokens"] > 32768
    assert ledger["requests_with_unknown_cost"] == 1
    assert ledger["requests"][0]["estimated_usd"] is None
    assert "offline-key" not in (tmp_path / "network_ledger.json").read_text()


@pytest.mark.parametrize("limits", [dict(max_requests=6, max_reserved_tokens=1, max_reserved_usd=0.25),
                                    dict(max_requests=6, max_reserved_tokens=160000, max_reserved_usd=0)])
def test_token_and_cost_caps_prevent_network(tmp_path, snapshot, limits):
    sent = []
    transport = BudgetTransport(tmp_path, delegate=httpx.MockTransport(lambda request: sent.append(request)), limits=limits)
    with OpenAI(api_key="offline-key", http_client=httpx.Client(transport=transport)) as client:
        report = ArticleClassifier(Settings(), client=client).classify([model_input(snapshot["articles"][0])])
    assert not sent and report.failed_ids


def test_ledger_prices_cached_tokens_and_retains_actual_model(tmp_path, snapshot):
    row = model_input(snapshot["articles"][0])

    def respond(request):
        return httpx.Response(200, json=dict(model="actual-snapshot", usage=dict(
            prompt_tokens=1000, completion_tokens=100, total_tokens=1100,
            prompt_tokens_details=dict(cached_tokens=500))))

    transport = BudgetTransport(tmp_path, delegate=httpx.MockTransport(respond))
    payload = ArticleClassifier.__new__(ArticleClassifier)
    payload.settings, payload.prompt = Settings(classification_model="gpt-4.1-mini"), "offline"
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions",
                            json=payload._request_arguments([row]))
    transport.handle_request(request)
    record = transport.ledger[0]
    assert record["returned_model"] == "actual-snapshot"
    assert record["estimated_usd"] == pytest.approx((500 * .4 + 500 * .1 + 100 * 1.6) / 1e6)


def test_luna_plan_uses_requested_model_for_both_configurations():
    plan = experiment_plan("gpt-6-luna")
    assert plan == [("luna-100", "gpt-6-luna", 100),
                    ("luna-repartitioned", "gpt-6-luna", 18)]


@pytest.mark.parametrize("write_tokens", [None, 200])
def test_luna_cache_write_pricing_is_accounted_and_budgeted(tmp_path, snapshot, write_tokens):
    details = dict(cached_tokens=500)
    if write_tokens is not None:
        details["cache_write_tokens"] = write_tokens

    def respond(request):
        return httpx.Response(200, json=dict(model="gpt-6-luna", usage=dict(
            prompt_tokens=1000, completion_tokens=100, total_tokens=1100,
            prompt_tokens_details=details)))

    transport = BudgetTransport(tmp_path, delegate=httpx.MockTransport(respond))
    settings = Settings(classification_model="gpt-6-luna")
    with OpenAI(api_key="offline-key", http_client=httpx.Client(transport=transport)) as client:
        classifier = ArticleClassifier(settings, client=client)
        arguments = classifier._request_arguments([model_input(snapshot["articles"][0])])
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions", json=arguments)
        transport.handle_request(request)
    record = transport.ledger[0]
    written = 500 if write_tokens is None else write_tokens
    expected = ((500 - written) * .1 + written * .125 + 500 * .01 + 100 * .5) / 1e6
    assert record["estimated_usd"] == pytest.approx(expected)
    assert record["cache_write_cost_assumed"] is (write_tokens is None)
    assert record["reserved_usd"] == pytest.approx(
        (record["reserved_input_tokens"] * .125 + record["reserved_output_tokens"] * .5) / 1e6)


def test_shared_enrichment_ledger_maps_plain_text_prompt_to_explicit_id(tmp_path):
    transport = BudgetTransport(tmp_path, delegate=httpx.MockTransport(
        lambda request: httpx.Response(200, json=dict(model="gpt-6-luna", usage=dict(
            prompt_tokens=10, completion_tokens=5, total_tokens=15)))))
    transport.article_ids_override = ("stable-enrichment-id",)
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions", json=dict(
        model="gpt-6-luna", max_completion_tokens=4096,
        messages=[dict(role="system", content="Return JSON only"),
                  dict(role="user", content="Ordinary rendered enrichment prompt, not JSON metadata")]))
    transport.handle_request(request)
    assert transport.ledger[0]["article_ids"] == ["stable-enrichment-id"]

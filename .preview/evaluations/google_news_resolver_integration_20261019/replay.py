"""Replay the frozen 42-wrapper benchmark through production code, with no network."""
from collections import Counter
import json
from pathlib import Path

import httpx

from research_automation.pipeline.google_news_resolver import GoogleNewsResolver

ROOT = Path(__file__).resolve().parents[3]
SAVED = ROOT / ".preview/evaluations/google_news_url_resolution_20261019"
OUT = Path(__file__).resolve().parent


def main():
    saved = json.loads((SAVED / "results.json").read_text(encoding="utf-8"))
    inputs = json.loads((SAVED / "dataset.json").read_text(encoding="utf-8"))["articles"]
    remaining = iter(saved["google_requests"])
    used = []

    def response(request):
        recorded = next(remaining)
        assert request.method == recorded["method"]
        assert str(request.url) == recorded["url"]
        used.append(recorded["method"])
        content = (SAVED / recorded["response_file"]).read_bytes()
        return httpx.Response(recorded["http_status"], content=content)

    rows = []
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        resolver = GoogleNewsResolver(client, sleep=lambda _: None)
        for item in inputs:
            result = resolver.resolve(item["url"], item["expected_domain"])
            rows.append(dict(article_id=item["article_id"], publisher=item["publisher"],
                             status=result.status, failure_reason=result.failure_reason,
                             resolved_url=result.resolved_url, request_count=result.request_count))
    assert next(remaining, None) is None
    result = dict(mode="offline replay of saved responses; no network or model calls",
                  wrappers=len(rows), requests_replayed=len(used),
                  statuses=dict(Counter(row["status"] for row in rows)), articles=rows)
    (OUT / "replay_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "articles"}))
    assert len(rows) == 42 and all(row["status"] == "resolved" for row in rows)


if __name__ == "__main__":
    main()

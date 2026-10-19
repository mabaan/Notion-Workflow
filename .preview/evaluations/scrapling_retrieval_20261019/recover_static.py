"""Correct setup-only static errors without repeating a baseline/article fetch."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import evaluate_scrapling_retrieval as bench

OUT = Path(__file__).resolve().parent
path = OUT / "run/results.jsonl"
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
backup = OUT / "run/setup_results.jsonl"
if not backup.exists():
    backup.write_bytes(path.read_bytes())
recovered = []
for index, row in enumerate(rows, 1):
    result = row["results"]["scrapling_static"]
    if result.get("reason") == "TypeError" or result["status"] == "configuration_error":
        item = {k:v for k,v in row.items() if k not in {"results", "fallback_used"}}
        result = bench.run_worker(item, "scrapling_static", OUT / ".venv/Scripts/python.exe")
        if result["status"] == "configuration_error":
            raise RuntimeError("Static API is still misconfigured; stop, do not count publisher failures")
        row["results"]["scrapling_static"] = result
        recovered.append(row["article_id"])
        print(f"{index}/{len(rows)}: {result['status']} - {row['publisher']}", flush=True)
    first, second = row["results"]["baseline"], row["results"]["scrapling_static"]
    if bench.should_render(row, first, second):
        raise RuntimeError("A genuinely eligible rendered candidate exists; install ordinary Playwright before completing this row")
    row["fallback_used"] = "none" if first["status"] == "extracted" else "scrapling_static" if second["status"] == "extracted" else "snippet_only"
    # Journal progress for safe resumability of configuration-only repairs.
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows), encoding="utf-8")
bench.write(OUT / "run/metrics.json", bench.summarize(rows))
bench.write(OUT / "run/setup_correction.json", dict(
    cause="curl_options is a curl Session constructor option, not a request keyword accepted by Scrapling's Fetcher.get forwarding. Removed; bounded content_callback and worker timeout remain.",
    setup_errors_before_any_static_http_request=len(recovered),
    baseline_fetches_repeated=0,
    corrected_static_ids=recovered,
    final_configuration_errors=sum(r['results']['scrapling_static']['status']=='configuration_error' for r in rows),
))

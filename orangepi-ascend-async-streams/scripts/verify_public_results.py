"""Verify only the public scalar evidence; no device, private logs or arrays needed."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT / "measurements/formal.json").read_text(encoding="utf-8"))
groups = defaultdict(list)
with (ROOT / "measurements/formal_windows.csv").open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        groups[(row["boundary"], int(row["window"]), row["policy"])].append(row)
assert len(groups) == 32 and sum(map(len, groups.values())) == 19200
for entry in summary["timings"]:
    rows = groups[(entry["boundary"], entry["window"], entry["policy"])]
    assert len(rows) == entry["samples"] == 600
    assert Counter(int(row["round"]) for row in rows) == {1: 200, 2: 200, 3: 200}
    for round_number in (1, 2, 3):
        assert sorted(int(row["iteration"]) for row in rows if int(row["round"]) == round_number) == list(range(1, 201))
    total = np.array([float(row["window_us"]) for row in rows])
    issue = np.array([float(row["issue_phase_us"]) for row in rows])
    wait = np.array([float(row["final_wait_us"]) for row in rows])
    assert np.isfinite(total).all() and np.all(total >= issue + wait)
    checks = {"median_window_us": np.median(total), "p95_window_us": np.percentile(total, 95),
              "mean_window_us": np.mean(total), "median_issue_phase_us": np.median(issue),
              "median_final_wait_us": np.median(wait),
              "mean_amortized_us_per_request": np.mean(total) / entry["window"],
              "requests_per_second_from_mean": entry["window"] * 1e6 / np.mean(total),
              "samples_per_second_from_mean": 32 * entry["window"] * 1e6 / np.mean(total)}
    for name, value in checks.items():
        assert np.isclose(entry[name], value, rtol=1e-12, atol=1e-9), name
assert summary["model_instance_count"] == 3
for value in summary["validation"].values():
    assert value["test_samples"] == 360 and value["correct"] == 352
    assert value["bitwise_equal_to_sync"] and value["max_abs_error_vs_sync"] == 0
probes = json.loads((ROOT / "measurements/probe-summary.json").read_text(encoding="utf-8"))
assert len(probes) == 4
assert {(p["default_stream"], p["sync_first"]) for p in probes} == {(False, False), (True, False), (False, True), (True, True)}
for probe in probes:
    assert probe["execute_async_ret"] == (500002 if probe["sync_first"] else 0)
    if probe["sync_first"]:
        assert probe["error_summary"] == "NnExecute not support mix execute"
    else:
        assert probe["synchronize_ret"] == 0 and probe["finite_output"]
print("PASS: 19200 public windows, 32 conditions, summary statistics and 4 redacted probes")

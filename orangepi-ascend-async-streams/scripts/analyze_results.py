"""Verify recovered evidence and render charts without connecting to any service."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
result = json.loads((ROOT / "results/formal.json").read_text(encoding="utf-8"))
groups = defaultdict(list)
with (ROOT / "results/formal_windows.csv").open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        key = (row["boundary"], int(row["window"]), row["policy"])
        assert float(row["window_us"]) >= float(row["issue_phase_us"]) + float(row["final_wait_us"])
        groups[key].append(row)
assert len(groups) == 32
assert sum(map(len, groups.values())) == 19200
for entry in result["timings"]:
    rows = groups[(entry["boundary"], entry["window"], entry["policy"])]
    values = [float(row["window_us"]) for row in rows]
    assert len(rows) == entry["samples"] == 600
    assert {int(row["round"]) for row in rows} == {1, 2, 3}
    for round_number in (1, 2, 3):
        assert sorted(int(row["iteration"]) for row in rows if int(row["round"]) == round_number) == list(range(1, 201))
    for key, value in [("mean_window_us", np.mean(values)), ("median_window_us", np.median(values)),
                       ("p95_window_us", np.percentile(values, 95))]:
        assert np.isclose(entry[key], value, rtol=1e-12, atol=1e-9)
    assert np.isclose(entry["requests_per_second_from_mean"], entry["window"] * 1e6 / np.mean(values))
with np.load(ROOT / "results/validation_sync_serial.npz") as archive:
    reference, labels = archive["logits"], archive["labels"]
for name, validation in result["validation"].items():
    with np.load(ROOT / f"results/validation_{name}.npz") as archive:
        np.testing.assert_array_equal(archive["logits"], reference)
        np.testing.assert_array_equal(archive["labels"], labels)
    assert reference.shape == (360, 10)
    assert int(np.sum(reference.argmax(axis=1) == labels)) == validation["correct"] == 352
assert hashlib.sha256((ROOT / "models/digits_b32.om").read_bytes()).hexdigest() == result["model_sha256"]
assert hashlib.sha256((ROOT / "models/test_data.npz").read_bytes()).hexdigest() == result["test_data_sha256"]
assert len(set(result["model_ids"])) == 3 and result["run_mode"] == 0
assert result["cleanup"] == "all ACL cleanup calls succeeded"

probes = []
for path in sorted((ROOT / "logs").glob("probe-*.log")):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("PROBE_RESULT="):
            entry = json.loads(line.split("=", 1)[1])
            entry["log"] = path.name
            probes.append(entry)
assert len(probes) == 4
assert all(entry["execute_async_ret"] == (500002 if entry.get("sync_first", False) else 0) for entry in probes)
(ROOT / "results/probe-summary.json").write_text(json.dumps(probes, indent=2), encoding="utf-8")
report = {"status": "passed", "completed_windows": 19200, "timing_conditions": 32,
          "windows_per_condition": 600, "independent_test_samples": 360,
          "correct_per_policy": 352, "bitwise_equal_logits_across_policies": True,
          "independent_model_ids": 3, "model_batch": 32,
          "probe_cases_verified": 4, "model_invocations_in_measured_windows":
          sum(key[1] * len(rows) for key, rows in groups.items())}
(ROOT / "results/verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

policies = [("sync_serial", "Synchronous serial", "#64748b"),
            ("async_wait_each", "Async + wait each", "#d97706"),
            ("async_wait_group", "Async + wait group", "#0f766e"),
            ("async_two_streams", "Async + two streams", "#2563eb")]
windows = [1, 4, 16, 64]
lookup = {(v["boundary"], v["window"], v["policy"]): v for v in result["timings"]}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})
fig, axes = plt.subplots(1, 3, figsize=(16.2, 5.4), constrained_layout=True)
for key, label, color in policies:
    for ax, boundary in zip(axes[:2], ("resident", "tensor_roundtrip")):
        values = [lookup[(boundary, w, key)]["mean_amortized_us_per_request"] for w in windows]
        ax.plot(range(4), values, marker="o", color=color, label=label, linewidth=2)
    rates = [lookup[("tensor_roundtrip", w, key)]["requests_per_second_from_mean"] for w in windows]
    axes[2].plot(range(4), rates, marker="o", color=color, label=label, linewidth=2)
for ax in axes:
    ax.set_xticks(range(4), windows)
    ax.set_xlabel("Requests per scheduling window (W)")
    ax.grid(axis="y", alpha=0.18)
    ax.set_ylim(bottom=0)
axes[0].set(title="Resident execution", ylabel="Mean window time / W (microseconds)")
axes[1].set(title="Tensor round trip", ylabel="Mean window time / W (microseconds)")
axes[2].set(title="Completed tensor-window throughput", ylabel="Model requests / second (batch=32)")
fig.suptitle("Orange Pi AIpro / Ascend310B1 / CANN 8.0.0\n"
             "Fixed model batch=32; 600 completed windows per condition", fontsize=14)
handles, labels_legend = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_legend, loc="outside lower center", ncol=4, frameon=False)
fig.savefig(ASSETS / "async-throughput.png", dpi=160, bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(12.6, 4.8), constrained_layout=True)
window = 64
for index, (key, label, color) in enumerate(policies):
    rows = groups[("resident", window, key)]
    issue = np.mean([float(row["issue_phase_us"]) for row in rows])
    wait = (np.mean([float(row["final_wait_us"]) for row in rows])
            if key in ("async_wait_group", "async_two_streams") else 0)
    total = np.mean([float(row["window_us"]) for row in rows])
    extra = total - issue - wait
    ax.barh(index, issue, color="#0f766e", label="API loop (includes per-call waits, where used)" if index == 0 else None)
    ax.barh(index, wait, left=issue, color="#f59e0b", label="Final stream drain" if index == 0 else None)
    ax.barh(index, extra, left=issue + wait, color="#cbd5e1", label="Wrapper overhead" if index == 0 else None)
    ax.text(total + 30, index, f"{total:,.1f} us", va="center", fontsize=10)
ax.set_yticks(range(4), [label for _, label, _ in policies])
ax.invert_yaxis()
ax.set_xlim(0, max(lookup[("resident", 64, key)]["mean_window_us"] for key, _, _ in policies) * 1.16)
ax.set(xlabel="Mean time for all 64 requests to complete (microseconds)",
       title="Submission alone leaves work outstanding\nResident inputs; arithmetic means from raw timing rows")
ax.grid(axis="x", alpha=0.15)
ax.legend(loc="lower right", frameon=False, fontsize=9)
fig.savefig(ASSETS / "submission-completion.png", dpi=160, bbox_inches="tight")
plt.close(fig)
print(json.dumps(report, indent=2))

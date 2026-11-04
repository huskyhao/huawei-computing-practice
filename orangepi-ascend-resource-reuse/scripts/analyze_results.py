"""Recompute statistics and validate evidence without CANN or third-party packages."""
import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ("reuse_all", "recreate_dataset", "reallocate_io", "reload_model")
STAGES = ("model_prepare_us", "memory_prepare_us", "dataset_prepare_us",
          "input_copy_us", "execute_us", "output_read_us", "dataset_release_us",
          "memory_release_us", "model_release_us", "python_gap_us")


def percentile(values, q):
    a = sorted(values)
    index = (len(a) - 1) * q
    lo, hi = math.floor(index), math.ceil(index)
    return a[lo] * (hi - index) + a[hi] * (index - lo) if lo != hi else a[lo]


def stats(values):
    assert values and all(math.isfinite(x) and x >= 0 for x in values)
    return {"count": len(values), "mean": statistics.mean(values),
            "median": statistics.median(values), "p95": percentile(values, .95),
            "min": min(values), "max": max(values)}


def analyze(base):
    formal = base / "formal"
    meta = json.loads((formal / "metadata.json").read_text(encoding="utf-8"))
    with (formal / "requests.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cfg = meta["configuration"]
    expected = cfg["rounds"] * cfg["repeats"] * len(POLICIES)
    assert len(rows) == expected == meta["rows"] == meta["timed_outputs_verified"]
    keys = [(int(r["round"]), r["policy"], int(r["sample"])) for r in rows]
    assert len(set(keys)) == len(rows)
    assert set(keys) == {(rnd, policy, sample) for rnd in range(cfg["rounds"])
                         for policy in POLICIES for sample in range(cfg["repeats"])}
    assert meta["batch"] == 32 and meta["run_mode"] == 0
    assert meta["input_bytes"] == 8192 and meta["output_bytes"] == 1280
    for rnd, order in enumerate(meta["round_order"]):
        desired = list(POLICIES)
        random.Random(cfg["seed"] + rnd).shuffle(desired)
        assert order == desired
        actual = []
        for row in rows:
            if int(row["round"]) == rnd and row["policy"] not in actual:
                actual.append(row["policy"])
        assert actual == order
    for row in rows:
        assert int(row["input_index"]) == int(row["sample"]) % 12
        values = [float(row[s]) for s in (*STAGES, "total_us")]
        assert all(math.isfinite(x) and x >= 0 for x in values)
        assert math.isclose(sum(float(row[s]) for s in STAGES),
                            float(row["total_us"]), abs_tol=1e-7)
        skipped = []
        if row["policy"] != "reload_model":
            skipped += ["model_prepare_us", "model_release_us"]
        if row["policy"] in ("reuse_all", "recreate_dataset"):
            skipped += ["memory_prepare_us", "memory_release_us"]
        if row["policy"] == "reuse_all":
            skipped += ["dataset_prepare_us", "dataset_release_us"]
        assert all(float(row[k]) == 0 for k in skipped)
    validation = meta["validation"]
    assert set(validation) == set(POLICIES)
    for v in validation.values():
        assert v["samples"] == 360 and v["correct"] / v["samples"] >= .95
        assert v["cpu_prediction_agreement"] == 1 and v["max_abs_vs_reuse"] == 0
    assert len({v["correct"] for v in validation.values()}) == 1
    summary = {"configuration": cfg, "total_timed_requests": len(rows),
               "batch": 32, "policy_statistics": {}, "validation": validation,
               "timer_pair_median_us": meta["timer_pair_median_us"], "startup": {}}
    for policy in POLICIES:
        group = [r for r in rows if r["policy"] == policy]
        counts = Counter(int(r["input_index"]) for r in group)
        # Each configured block contains an equal number of all 12 padded batches.
        if cfg["repeats"] % 12 == 0:
            assert len(set(counts.values())) == 1 and len(counts) == 12
        summary["policy_statistics"][policy] = {
            "total_us": stats([float(r["total_us"]) for r in group]),
            "stage_mean_us": {s: statistics.mean(float(r[s]) for r in group) for s in STAGES},
            "round_mean_us": [statistics.mean(float(r["total_us"]) for r in group
                                              if int(r["round"]) == rnd)
                              for rnd in range(cfg["rounds"])],
        }
    reuse = summary["policy_statistics"]["reuse_all"]["total_us"]["mean"]
    for p in summary["policy_statistics"].values():
        p["relative_to_reuse_mean"] = p["total_us"]["mean"] / reuse
    with (base / "startup" / "processes.csv").open(newline="", encoding="utf-8") as f:
        startup = list(csv.DictReader(f))
    assert [int(r["process"]) for r in startup] == list(range(len(startup)))
    assert all(int(r["first_batch_correct"]) >= 30 for r in startup)
    for col in startup[0]:
        if col not in ("process", "first_batch_correct"):
            summary["startup"][col] = stats([float(r[col]) for r in startup])
    summary["startup_processes"] = len(startup)
    summary["sha256"] = meta["sha256"]
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", type=Path, default=None)
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    base = args.base or (ROOT / "measurements" if (ROOT / "measurements").exists()
                         else ROOT / "results")
    summary = analyze(base)
    path = base / "summary.json"
    if args.write:
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif path.exists():
        assert json.loads(path.read_text(encoding="utf-8")) == summary, "Saved summary mismatch"
    print(json.dumps({"status": "PASS", "requests": summary["total_timed_requests"],
                      "startup_processes": summary["startup_processes"],
                      "policies": {p: v["total_us"] for p, v in summary["policy_statistics"].items()}},
                     indent=2))

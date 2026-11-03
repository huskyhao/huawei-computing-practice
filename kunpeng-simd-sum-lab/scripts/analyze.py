#!/usr/bin/env python3
"""Recompute all published statistics from the unfiltered batch records."""
import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ["scalar", "auto_o2", "auto_o3", "auto_tuned", "neon4"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with (ROOT / "measurements/raw.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    metadata = (ROOT / "measurements/bench.stderr.txt").read_text()
    match = re.search(r"BENCH cpu=(\d+) affinity_count=1 rounds=(\d+)", metadata)
    assert match, "Missing single-CPU benchmark metadata"
    cpu, rounds = map(int, match.groups())
    assert len(rows) == 2 * len(VARIANTS) * rounds
    summary = {"unit": "GiB/s = logical input bytes / elapsed seconds / 2**30",
               "samples": len(rows), "cpu": cpu, "rounds": rounds,
               "statistics": "median, min, max across batch means; no filtering",
               "results": []}
    lines = ["| 工作集 | 实现 | 中位耗时（µs/次） | 逻辑吞吐（GiB/s） | 吞吐范围 | 相对标量加速 |",
             "|---|---|---:|---:|---:|---:|"]
    for size in sorted({int(r["bytes"]) for r in rows}):
        baseline = statistics.median(float(r["ns_per_scan"]) for r in rows
                                     if int(r["bytes"]) == size and r["variant"] == "scalar")
        for name in VARIANTS:
            group = [r for r in rows if int(r["bytes"]) == size and r["variant"] == name]
            assert {int(r["round"]) for r in group} == set(range(rounds))
            assert len({r["expected_sum"] for r in group}) == 1
            assert all(int(r["cpu_start"]) == int(r["cpu_end"]) == cpu for r in group)
            assert all(float(r["elapsed_s"]) > 0 for r in group)
            for r in group:
                expected_ns = float(r["elapsed_s"]) * 1e9 / int(r["reps"])
                assert abs(expected_ns - float(r["ns_per_scan"])) / expected_ns < 1e-6
                expected_gib = size * int(r["reps"]) / float(r["elapsed_s"]) / 2**30
                assert abs(expected_gib - float(r["logical_gib_s"])) / expected_gib < 1e-5
            ns = [float(r["ns_per_scan"]) for r in group]
            gib = [float(r["logical_gib_s"]) for r in group]
            item = {"bytes": size, "variant": name, "rounds": len(group),
                    "reps_per_batch": int(group[0]["reps"]), "expected_sum": group[0]["expected_sum"],
                    "median_us": statistics.median(ns) / 1000,
                    "median_gib_s": statistics.median(gib), "min_gib_s": min(gib),
                    "max_gib_s": max(gib), "speedup_vs_scalar": baseline / statistics.median(ns)}
            summary["results"].append(item)
            label = "256 KiB" if size == 262144 else "256 MiB"
            lines.append(f"| {label} | `{name}` | {item['median_us']:.3f} | "
                         f"{item['median_gib_s']:.2f} | {min(gib):.2f}–{max(gib):.2f} | "
                         f"{item['speedup_vs_scalar']:.2f}× |")
    (ROOT / "measurements/summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                                  encoding="utf-8", newline="\n")
    (ROOT / "measurements/table.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

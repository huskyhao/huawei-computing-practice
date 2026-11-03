#!/usr/bin/env python3
"""Recompute all statistics from both unfiltered architecture-mode CSV files."""
import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = ["shared", "packed8", "stride64", "stride128", "stride256"]

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    combined, results, tables = [], [], []
    metadata = {}
    for mode in ("lse", "llsc"):
        with (ROOT / f"measurements/raw-{mode}.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        log = (ROOT / f"measurements/bench-{mode}.stderr.txt").read_text()
        match = re.search(r"BENCH rounds=(\d+) iterations_per_worker=(\d+) controller_cpu=(\d+) worker_cpus=([\d;]+)", log)
        assert match, "Missing benchmark metadata"
        rounds, iterations, controller = map(int, match.groups()[:3])
        cpus = [int(c) for c in match[4].strip(";").split(";")]
        assert len(rows) == rounds * 20 and "BENCH PASS" in log
        metadata[mode] = {"rounds": rounds, "iterations_per_worker": iterations,
                          "controller_cpu": controller, "worker_cpus": cpus}
        for r in rows:
            threads, elapsed = int(r["threads"]), int(r["elapsed_ns"])
            assert threads in (1, 2, 4, 8) and r["layout"] in LAYOUTS
            assert int(r["iterations_per_worker"]) == iterations
            assert int(r["actual_sum"]) == int(r["total_ops"]) == threads * iterations
            assert int(r["base_alignment"]) == 4096
            assert r["worker_cpus"] == ";".join(map(str, cpus[:threads]))
            assert elapsed > 0 and int(r["start_skew_ns"]) <= elapsed
            expected = threads * iterations * 1000 / elapsed
            assert abs(float(r["total_mops"]) - expected) / expected < 1e-5
            combined.append({"atomic_mode": mode, **r})
        for round_id in range(rounds):
            group = [r for r in rows if int(r["round"]) == round_id]
            assert len(group) == 20 and {int(r["order"]) for r in group} == set(range(20))
            assert len({(r["threads"], r["layout"]) for r in group}) == 20
        lines = ["| 线程数 | 共享单计数器 | 间距 8 B | 间距 64 B | 间距 128 B | 间距 256 B |",
                 "|---:|---:|---:|---:|---:|---:|"]
        for threads in (1, 2, 4, 8):
            entries = []
            for name in LAYOUTS:
                group = [r for r in rows if int(r["threads"]) == threads and r["layout"] == name]
                assert len(group) == rounds
                elapsed = [int(r["elapsed_ns"]) for r in group]
                throughput = [threads * iterations * 1000 / n for n in elapsed]
                item = {"atomic_mode": mode, "threads": threads, "layout": name, "rounds": rounds,
                        "median_mops": statistics.median(throughput),
                        "min_mops": min(throughput), "max_mops": max(throughput),
                        "median_ms": statistics.median(elapsed) / 1e6,
                        "max_start_skew_us": max(int(r["start_skew_ns"]) for r in group) / 1000}
                results.append(item); entries.append(f"{item['median_mops']:.2f}")
            lines.append("| " + " | ".join([str(threads)] + entries) + " |")
        table = "\n".join(lines) + "\n"
        (ROOT / f"measurements/table-{mode}.md").write_text(table, encoding="utf-8", newline="\n")
        tables.append(mode.upper() + " (Mops/s)\n" + table)
    assert metadata["lse"] == metadata["llsc"]
    summary = {"unit": "million atomic increments per second; total across workers",
               "samples": len(combined), "metadata": metadata,
               "statistics": "median/min/max across all batches; no filtering", "results": results}
    (ROOT / "measurements/summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    with (ROOT / "measurements/raw.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(combined[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(combined)
    validation_results = []
    if (ROOT / "validation/raw-lse.csv").exists():
        validation_lines = ["| 原子实现 | 布局 | 中位吞吐 Mops/s | 最小–最大 Mops/s |",
                            "|---|---|---:|---:|"]
        for mode in ("lse", "llsc"):
            with (ROOT / f"validation/raw-{mode}.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            log = (ROOT / f"validation/bench-{mode}.stderr.txt").read_text()
            assert "BENCH rounds=3 iterations_per_worker=8000000" in log and "BENCH PASS samples=60" in log
            assert len(rows) == 60
            for r in rows:
                t, n = int(r["threads"]), int(r["elapsed_ns"])
                assert int(r["actual_sum"]) == int(r["total_ops"]) == t * 8000000
                assert int(r["base_alignment"]) == 4096
                assert r["worker_cpus"] == ";".join(map(str, cpus[:t]))
                assert n > 0
                expected = t * 8000000 * 1000 / n
                assert abs(float(r["total_mops"]) - expected) / expected < 1e-5
            for round_id in range(3):
                group=[r for r in rows if int(r["round"])==round_id]
                assert len(group)==20 and {int(r["order"]) for r in group}==set(range(20))
                assert len({(r["threads"],r["layout"]) for r in group})==20
            for t in (1,2,4,8):
                for layout in LAYOUTS:
                    values=[t*8000000*1000/int(r["elapsed_ns"]) for r in rows
                            if int(r["threads"])==t and r["layout"]==layout]
                    assert len(values)==3
                    item={"atomic_mode":mode,"threads":t,"layout":layout,"rounds":3,
                          "median_mops":statistics.median(values),"min_mops":min(values),"max_mops":max(values)}
                    validation_results.append(item)
                    if t==8:
                        validation_lines.append(f"| {mode.upper()} | `{layout}` | {item['median_mops']:.2f} | "
                                                f"{item['min_mops']:.2f}–{item['max_mops']:.2f} |")
        (ROOT/"validation/summary.json").write_text(json.dumps({"samples":120,"results":validation_results},indent=2)+"\n",encoding="utf-8",newline="\n")
        (ROOT/"validation/table-8threads.md").write_text("\n".join(validation_lines)+"\n",encoding="utf-8",newline="\n")
    print("\n".join(tables))

if __name__ == "__main__":
    main()

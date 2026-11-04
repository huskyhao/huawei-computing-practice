#!/usr/bin/env python3
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    metadata=json.loads((ROOT/"measurements/run.json").read_text())
    environment=json.loads((ROOT/"measurements/environment.json").read_text())
    with (ROOT/"measurements/raw.csv").open(newline="") as f:rows=list(csv.DictReader(f))
    with (ROOT/"measurements/placement.csv").open(newline="") as f:placements=list(csv.DictReader(f))
    rounds=metadata["rounds"];size=metadata["mib"]*1024*1024
    assert len(rows)==8*2*rounds and len(placements)==16
    for p in placements:
        counts=[int(p[f"node{i}"]) for i in range(4)]
        assert sum(counts)==int(p["pages"])==size//int(p["page_size"])
        assert counts[int(p["memory_node"])]==int(p["pages"])
    for r in rows:
        assert int(r["bytes"])==size and int(r["slots"])==size//128
        assert r["cpu_start"]==r["cpu_end"]==r["cpu"] and r["checksum_ok"]=="1"
        elapsed=float(r["elapsed_s"]);reps=int(r["reps"])
        expected=elapsed*1e9/(reps*size//128) if r["pattern"]=="chase" else size*reps/elapsed/2**30
        measured=float(r["ns_per_hop"] if r["pattern"]=="chase" else r["logical_gib_s"])
        assert abs(expected-measured)/expected<1e-5
    results=[]
    table=["| 运行 CPU（节点） | 内存节点 | distance | 依赖读取 ns/跳 | 范围 ns/跳 | 顺序读取 GiB/s | 范围 GiB/s |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for cpu,cpu_node in ((4,0),(52,2)):
        for node in range(4):
            entry={"cpu":cpu,"cpu_node":cpu_node,"memory_node":node,
                   "distance":environment["nodes"][str(cpu_node)]["distances"][node]}
            for pattern,metric in (("chase","ns_per_hop"),("scan","logical_gib_s")):
                group=[r for r in rows if int(r["cpu"])==cpu and int(r["memory_node"])==node and r["pattern"]==pattern]
                assert len(group)==rounds and {int(r["round"]) for r in group}==set(range(rounds))
                values=[float(r[metric]) for r in group]
                entry[pattern]={"median":statistics.median(values),"min":min(values),"max":max(values)}
            results.append(entry)
            c,s=entry["chase"],entry["scan"]
            table.append(f"| {cpu}（{cpu_node}） | {node} | {entry['distance']} | {c['median']:.2f} | "
                         f"{c['min']:.2f}–{c['max']:.2f} | {s['median']:.2f} | {s['min']:.2f}–{s['max']:.2f} |")
    summary={"samples":len(rows),"page_checks":len(placements),"statistics":"median/min/max of batch means; no filtering",
             "results":results}
    (ROOT/"measurements/summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8",newline="\n")
    (ROOT/"measurements/table.md").write_text("\n".join(table)+"\n",encoding="utf-8",newline="\n")
    print("\n".join(table))

if __name__=="__main__":main()

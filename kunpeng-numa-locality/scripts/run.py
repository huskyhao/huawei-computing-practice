#!/usr/bin/env python3
"""Run one-core jobs in randomized order; preserve complete stdout per job."""
import csv
import json
import os
import random
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"measurements"
def stamp():return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")

def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/"raw.csv").exists() or (OUT/"job-0.stdout.txt").exists():
        raise SystemExit("Existing results: copy sources into a new directory to rerun")
    rounds=int(os.environ.get("ROUNDS","9"));mib=int(os.environ.get("MIB","256"))
    jobs=[(cpu,node) for cpu in (4,52) for node in range(4)]
    random.Random(20261104).shuffle(jobs)
    metadata={"rounds":rounds,"mib":mib,"seed":20261104,"job_order":jobs,"start":stamp()}
    samples=[];placements=[]
    for job,(cpu,node) in enumerate(jobs):
        command=[os.environ.get("NUMACTL","numactl"),f"--physcpubind={cpu}",f"--membind={node}",
                 str(ROOT/"build/bench"),str(cpu),str(node),str(rounds),str(mib)]
        with (OUT/f"job-{job}.stdout.txt").open("w") as stdout,(OUT/f"job-{job}.stderr.txt").open("w") as stderr:
            subprocess.run(command,stdout=stdout,stderr=stderr,check=True)
        for row in csv.reader((OUT/f"job-{job}.stdout.txt").open(newline="")):
            if row[0]=="SAMPLE":samples.append([job]+row[1:])
            elif row[0]=="PLACEMENT":placements.append([job]+row[1:])
            else:raise ValueError("Unexpected record")
        print(f"JOB {job+1}/8 PASS cpu={cpu} memory_node={node}",flush=True)
    with (OUT/"raw.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(["job","cpu","memory_node","round","order","pattern","bytes","slots","reps","elapsed_s",
                         "ns_per_hop","logical_gib_s","cpu_start","cpu_end","checksum_ok"])
        writer.writerows(samples)
    with (OUT/"placement.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(["job","phase","cpu","memory_node","pages","page_size","node0","node1","node2","node3"])
        writer.writerows(placements)
    metadata["end"]=stamp()
    (OUT/"run.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8",newline="\n")
    subprocess.run(["python3",str(ROOT/"scripts/analyze.py")],check=True)

if __name__=="__main__":main()

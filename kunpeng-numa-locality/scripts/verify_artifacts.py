#!/usr/bin/env python3
"""Check measured source identity, complete raw records, page placement and blog."""
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
for line in (ROOT/"measurements/source-sha256.txt").read_text().splitlines():
    digest,path=line.split(maxsplit=1)
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
subprocess.run([sys.executable,str(ROOT/"scripts/analyze.py")],check=True,stdout=subprocess.DEVNULL)
metadata=json.loads((ROOT/"measurements/run.json").read_text())
with (ROOT/"measurements/raw.csv").open(newline="") as f:
    reader=csv.DictReader(f);keys=reader.fieldnames;rows=list(reader)
with (ROOT/"measurements/placement.csv").open(newline="") as f:
    reader=csv.DictReader(f);page_keys=reader.fieldnames;pages=list(reader)
reconstructed=[];reconstructed_pages=[]
for job,(cpu,node) in enumerate(metadata["job_order"]):
    for raw in csv.reader((ROOT/f"measurements/job-{job}.stdout.txt").open(newline="")):
        if raw[0]=="SAMPLE":reconstructed.append(dict(zip(keys,map(str,[job]+raw[1:]),strict=True)))
        elif raw[0]=="PLACEMENT":reconstructed_pages.append(dict(zip(page_keys,map(str,[job]+raw[1:]),strict=True)))
        else:raise AssertionError("Unexpected stdout record")
    stderr=(ROOT/f"measurements/job-{job}.stderr.txt").read_text()
    assert f"CORRECTNESS PASS cpu={cpu} memory_node={node}" in stderr
    assert f"BENCH PASS cpu={cpu} memory_node={node} samples={metadata['rounds']*2}" in stderr
    group=[r for r in rows if int(r["job"])==job]
    for round_id in range(metadata["rounds"]):
        pair=[r for r in group if int(r["round"])==round_id]
        assert len(pair)==2 and {r["pattern"] for r in pair}=={"chase","scan"}
        assert {r["order"] for r in pair}=={"0","1"}
    placed=[p for p in pages if int(p["job"])==job]
    assert len(placed)==2 and {p["phase"] for p in placed}=={"before","after"}
    assert all(int(p["cpu"])==cpu and int(p["memory_node"])==node for p in placed)
assert rows==reconstructed and pages==reconstructed_pages
ubsan=(ROOT/"measurements/ubsan.stderr.txt").read_text()
assert "CORRECTNESS PASS" in ubsan and "BENCH PASS" in ubsan and "runtime error" not in ubsan
blog=(ROOT/"blog.md").read_text(encoding="utf-8")
assert (ROOT/"measurements/table.md").read_text(encoding="utf-8").strip() in blog
for name in ("README.md","blog.md","sources.md","PUBLICATION.md"):
    for link in re.findall(r"\]\(([^)]+)\)",(ROOT/name).read_text(encoding="utf-8")):
        if "://" not in link and not link.startswith("#"):
            assert (ROOT/link.split("#")[0]).exists(),link
assert (ROOT/"assets/numa-latency-throughput.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
for p in ROOT.rglob("*"):
    if not p.is_file() or p.suffix==".png" or any(c in {".git","build","__pycache__","private"} for c in p.parts):continue
    text=p.read_text(encoding="utf-8")
    assert not re.search(r"(?i)/(?:home|Users)/|[A-Z]:[\\/]Users[\\/]|/(?:nix)/store/|BEGIN [A-Z ]*PRIVATE KEY",text),p
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b",text),p
print(f"PASS: source hashes, {len(rows)} complete samples, {len(pages)} full-page placement checks, checksums, blog table and links")

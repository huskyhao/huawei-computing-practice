#!/usr/bin/env python3
"""Check source provenance, raw data consistency, and generated deliverables."""
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for line in (ROOT / "measurements/source-sha256.txt").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
subprocess.run([sys.executable, str(ROOT / "scripts/analyze.py")], check=True,
               stdout=subprocess.DEVNULL)
with (ROOT / "measurements/raw.csv").open(newline="") as f:
    rows = list(csv.DictReader(f))
for size in {r["bytes"] for r in rows}:
    group = [r for r in rows if r["bytes"] == size]
    assert len({r["expected_sum"] for r in group}) == 1
    for round_id in {r["round"] for r in group}:
        batch = [r for r in group if r["round"] == round_id]
        assert len(batch) == 5
        assert {r["order"] for r in batch} == {"0", "1", "2", "3", "4"}
for name in ["bench", "ubsan"]:
    log = (ROOT / f"measurements/{name}.stderr.txt").read_text()
    assert "SELFTEST PASS checks=15480" in log
    assert "runtime error" not in log
assert "BENCH PASS" in (ROOT / "measurements/bench.stderr.txt").read_text()
for name in ["auto_o3", "auto_tuned"]:
    assert "loop vectorized using 16 byte vectors" in (ROOT / f"measurements/{name}.vectorization.txt").read_text()
assert "vectorized 0 loops" in (ROOT / "measurements/auto_o2.vectorization.txt").read_text()
assert (ROOT / "measurements/neon4.s").read_text().count("uadalp") == 4
table = (ROOT / "measurements/table.md").read_text(encoding="utf-8").strip()
blog = (ROOT / "blog.md").read_text(encoding="utf-8")
assert table in blog, "Blog table must exactly match the recomputed measurements"
for file in [ROOT / "blog.md", ROOT / "README.md"]:
    for link in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
        if "://" not in link and not link.startswith("#"):
            assert (file.parent / link.split("#")[0]).exists(), link
assert (ROOT / "assets/throughput.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
print(f"PASS: source hashes, {len(rows)} raw batches, checksums, compiler reports, blog table and links")

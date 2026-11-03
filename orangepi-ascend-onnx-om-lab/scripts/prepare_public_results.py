"""Publish only whitelisted numerical results; preserve original evidence locally."""
import csv
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results"
DESTINATION = ROOT / "measurements"
DESTINATION.mkdir(exist_ok=True)


def remove_machine_paths(value):
    if isinstance(value, dict):
        return {key: remove_machine_paths(item) for key, item in value.items() if key != "filepath"}
    if isinstance(value, list):
        return [remove_machine_paths(item) for item in value]
    return value


for name in ("training.json", "benchmark.json", "cpu-thread-check.json"):
    source = json.loads((SOURCE / name).read_text(encoding="utf-8"))
    clean = remove_machine_paths(source)
    serialized = json.dumps(clean, indent=2)
    assert not re.search(r"/home/|/usr/local/|[A-Za-z]:[\\/]", serialized)
    (DESTINATION / name).write_text(serialized + "\n", encoding="utf-8")

fields = ["batch", "scenario", "round", "iteration", "latency_us"]
scenarios = {"cpu_numpy_t1", "cpu_numpy_t4", "npu_execute", "npu_tensor_roundtrip"}
with (SOURCE / "latency_samples.csv").open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    assert reader.fieldnames == fields
    rows = list(reader)
    for row in rows:
        assert int(row["batch"]) in (1, 32, 128)
        assert row["scenario"] in scenarios
        assert 1 <= int(row["round"]) <= 3
        assert 1 <= int(row["iteration"]) <= 500
        assert math.isfinite(float(row["latency_us"])) and float(row["latency_us"]) > 0
    assert len(rows) == 18000
with (DESTINATION / "latency_samples.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

packages = (SOURCE / "requirements-resolved.txt").read_text(encoding="utf-8")
assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+\-]+", line)
           for line in packages.splitlines())
(DESTINATION / "requirements-resolved.txt").write_text(packages, encoding="utf-8")
print("Prepared public results: 3 path-redacted JSON summaries, 18000 numeric timing rows, package versions.")

#!/usr/bin/env python3
"""Collect only experiment-relevant, public-safe topology and version fields."""
import json
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def read(path):
    p = Path(path)
    return p.read_text().strip() if p.exists() else None

allowed_fields = {"Architecture", "Byte Order", "CPU(s)", "Vendor ID", "Model name",
                  "Thread(s) per core", "Core(s) per socket", "Socket(s)", "NUMA node(s)"}
cpu = {}
for line in subprocess.check_output(["lscpu"], text=True).splitlines():
    name, sep, value = line.partition(":")
    if sep and name in allowed_fields:
        cpu[name] = value.strip()
os_fields = {}
for line in Path("/etc/os-release").read_text().splitlines():
    name, sep, value = line.partition("=")
    if sep and name in {"ID", "VERSION_ID", "PRETTY_NAME"}:
        os_fields[name] = value.strip('"')
topology = {}
selected = [int(c) for c in os.environ.get("CPUS", "4,5,6,7,8,9,10,11").split(",")]
selected.append(int(os.environ.get("CONTROLLER", "12")))
for cpu_id in sorted(set(selected)):
    path = Path(f"/sys/devices/system/cpu/cpu{cpu_id}")
    cache = []
    for index in sorted((path / "cache").glob("index*")):
        cache.append({key: read(index / key) for key in
                      ["level", "type", "size", "coherency_line_size", "shared_cpu_list"]})
    topology[str(cpu_id)] = cache
result = {"date": datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
          "timezone": "Asia/Shanghai", "kernel": platform.release(), "os": os_fields,
          "cpu": cpu, "topology": topology,
          "numa_balancing": read("/proc/sys/kernel/numa_balancing"),
          "thp": read("/sys/kernel/mm/transparent_hugepage/enabled"),
          "collection": "allowlist; no host/user identifiers, private paths, load or vulnerability details"}
print(json.dumps(result, indent=2))

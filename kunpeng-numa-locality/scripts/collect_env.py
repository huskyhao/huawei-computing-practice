#!/usr/bin/env python3
"""Only publish topology/version/policy fields, never connection identifiers."""
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

def read(path):
    p=Path(path)
    return p.read_text().strip() if p.exists() else None

cpu_fields={"Architecture","Byte Order","CPU(s)","Vendor ID","Model name",
            "Socket(s)","Core(s) per socket","Thread(s) per core","NUMA node(s)"}
cpu={}
for line in subprocess.check_output(["lscpu"],text=True).splitlines():
    k,sep,v=line.partition(":")
    if sep and k in cpu_fields:cpu[k]=v.strip()
os_info={}
for line in Path("/etc/os-release").read_text().splitlines():
    k,sep,v=line.partition("=")
    if sep and k in {"ID","VERSION_ID","PRETTY_NAME"}:os_info[k]=v.strip('"')
groups={}
nodes={}
for node in range(4):
    root=Path(f"/sys/devices/system/node/node{node}")
    cpu_id=int(read(root/"cpulist").split("-")[0].split(",")[0])
    package=read(f"/sys/devices/system/cpu/cpu{cpu_id}/topology/physical_package_id")
    if package not in groups:groups[package]=len(groups)
    nodes[str(node)]={"cpus":read(root/"cpulist"),"distances":list(map(int,read(root/"distance").split())),
                      "socket_group":groups[package]}
cache={}
for cpu_id in (4,52):
    cache[str(cpu_id)]=[{k:read(d/k) for k in ("level","type","size","coherency_line_size","shared_cpu_list")}
                       for d in sorted(Path(f"/sys/devices/system/cpu/cpu{cpu_id}/cache").glob("index*"))]
print(json.dumps({"date":datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),"timezone":"Asia/Shanghai",
                  "kernel":platform.release(),"os":os_info,"cpu":cpu,"nodes":nodes,"caches":cache,
                  "automatic_numa_balancing":read("/proc/sys/kernel/numa_balancing"),
                  "global_thp_policy":read("/sys/kernel/mm/transparent_hugepage/enabled"),
                  "test_mapping_thp":"MADV_NOHUGEPAGE required", "collection":"public allowlist"},indent=2))

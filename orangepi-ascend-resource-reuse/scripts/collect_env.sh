#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
label="$1"
if [ -z "$label" ]; then label=before; fi
{
  date --iso-8601=seconds
  uname -srm
  cat /etc/os-release
  lscpu
  free -h
  uptime
  vmstat 1 3
  ps -eo stat,pcpu,comm --sort=-pcpu | head -20
  npu-smi info
  npu-smi info -t health -i 0 -c 0
  cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg
} > "logs/environment-$label.txt" 2>&1

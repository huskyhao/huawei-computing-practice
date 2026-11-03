#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
{
  date --iso-8601=seconds
  uname -srm
  cat /etc/os-release
  lscpu
  free -h
  df -h .
  uptime
  npu-smi info
  npu-smi info -t health -i 0 -c 0
  cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg
  vmstat 1 3
} 2>&1 | tee logs/environment.txt

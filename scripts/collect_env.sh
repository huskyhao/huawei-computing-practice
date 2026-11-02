#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs results
{
  date --iso-8601=seconds
  uname -srm
  cat /etc/os-release
  lscpu
  free -h
  df -h .
  uptime
  ps -eo comm,pcpu,pmem --sort=-pcpu | head -n 12
  npu-smi info
  npu-smi info -t health -i 0 -c 0
  cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg
  python3 --version
  python3 -m pip show numpy scikit-learn protobuf | sed -n '/^Name:/p; /^Version:/p'
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
  python3 -c 'import acl; print("acl_path:", acl.__file__); print("soc_name:", acl.get_soc_name()); print("acl.init:", acl.init()); print("device_count:", acl.rt.get_device_count()); print("run_mode:", acl.rt.get_run_mode()); print("acl.finalize:", acl.finalize())'
} 2>&1 | tee logs/environment.txt

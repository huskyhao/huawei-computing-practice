#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /usr/local/Ascend/ascend-toolkit/set_env.sh
EXPERIMENT_VENV="${EXPERIMENT_VENV:-${PWD}/.venv}"
source "${EXPERIMENT_VENV}/bin/activate"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p results logs
python -m pip freeze > results/requirements-resolved.txt
python scripts/async_experiment.py "$@" 2>&1 | tee logs/run.log
{
  date --iso-8601=seconds
  npu-smi info
  npu-smi info -t health -i 0 -c 0
  uptime
} > logs/environment-after.txt

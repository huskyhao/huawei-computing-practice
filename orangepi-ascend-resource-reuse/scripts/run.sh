#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /usr/local/Ascend/ascend-toolkit/set_env.sh
if [ -z "$EXPERIMENT_VENV" ]; then EXPERIMENT_VENV="$PWD/.venv"; fi
source "$EXPERIMENT_VENV/bin/activate"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p results logs
python scripts/resource_lab.py "$@" 2>&1 | tee logs/latest-run.log

#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source .venv/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python scripts/train_export.py 2>&1 | tee logs/train.log
bash scripts/convert.sh
python scripts/benchmark.py --warmup 50 --repeats 500 --rounds 3 2>&1 | tee logs/benchmark.log
npu-smi info > logs/npu-after.txt
npu-smi info -t health -i 0 -c 0 >> logs/npu-after.txt
uptime >> logs/npu-after.txt

#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source .venv/bin/activate
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TE_PARALLEL_COMPILER=2
python scripts/train_export.py 2>&1 | tee logs/rebuild-training.log
SOC_VERSION=$(python -c 'import acl; print(acl.get_soc_name())')
python scripts/time_command.py logs/rebuild-atc.time \
  atc --framework=5 --model=models/digits_b32.onnx --output=models/digits_b32 \
  --soc_version="$SOC_VERSION" --input_format=ND --input_shape="input:32,64" \
  --precision_mode=allow_fp32_to_fp16 --log=error 2>&1 | tee logs/rebuild-atc.log
sha256sum models/* > results/input-sha256.txt

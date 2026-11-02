#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source .venv/bin/activate
mkdir -p logs models results
SOC_VERSION=$(python -c 'import acl; print(acl.get_soc_name())')
printf 'Detected SoC: %s\n' "$SOC_VERSION" | tee logs/soc.txt
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export TE_PARALLEL_COMPILER=2 MAX_COMPILE_CORE_NUMBER=2
for batch in 1 32 128; do
  python scripts/time_command.py "logs/atc_b${batch}.time" \
    atc --framework=5 --model="models/digits_b${batch}.onnx" \
    --output="models/digits_b${batch}" --soc_version="$SOC_VERSION" \
    --input_format=ND --input_shape="input:${batch},64" \
    --precision_mode=allow_fp32_to_fp16 --log=error 2>&1 | tee "logs/atc_b${batch}.log"
done
sha256sum models/*.onnx models/*.om > results/model-sha256.txt

#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p models logs results
BASELINE_DIR="${BASELINE_DIR:-${HOME}/hw/ascend310b-digits-onnx-om}"
for name in digits_b32.om digits_b32.onnx test_data.npz weights.npz; do
  cp "${BASELINE_DIR}/models/${name}" "models/${name}"
done
sha256sum models/* > results/input-sha256.txt
printf 'Reused fixed batch-32 model and held-out inputs from the 2026-11-02 baseline.\n' > logs/model-provenance.txt

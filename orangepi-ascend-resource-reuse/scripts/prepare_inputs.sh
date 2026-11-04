#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
if [ -z "$BASELINE_DIR" ]; then BASELINE_DIR="$HOME/hw/ascend310b-digits-onnx-om"; fi
mkdir -p models logs results
for name in digits_b32.om digits_b32.onnx test_data.npz weights.npz; do
  cp "$BASELINE_DIR/models/$name" "models/$name"
done
sha256sum models/* > results/input-sha256.txt

#!/usr/bin/env bash
# Reuse the EXACT primary binaries: 4x work per thread, 3 new randomized rounds.
set -euo pipefail
cd "$(dirname "$0")/.."
export LC_ALL=C TZ=Asia/Shanghai
CPUS=${CPUS:-4,5,6,7,8,9,10,11}
CONTROLLER=${CONTROLLER:-12}
if [[ -e validation/raw-lse.csv || -e validation/raw-llsc.csv ]]; then
  echo 'Validation results exist; use a new directory to rerun.' >&2; exit 1
fi
mkdir -p validation
date --iso-8601=seconds > validation/timing-start.txt
for mode in lse llsc; do
  "build/bench-$mode" --cpus "$CPUS" --controller "$CONTROLLER" --rounds 3 --iterations 8000000 \
    > "validation/raw-$mode.csv" 2> "validation/bench-$mode.stderr.txt"
done
date --iso-8601=seconds > validation/timing-end.txt
sha256sum scripts/validate_longer.sh > validation/script-sha256.txt

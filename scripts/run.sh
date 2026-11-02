#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export LC_ALL=C TZ=Asia/Shanghai
CXX=${CXX:-g++}
export CPUS=${CPUS:-4,5,6,7,8,9,10,11}
export CONTROLLER=${CONTROLLER:-12}
ROUNDS=${ROUNDS:-9}
ITERATIONS=${ITERATIONS:-2000000}
if [[ $(uname -m) != aarch64 ]]; then echo 'AArch64 Linux required' >&2; exit 1; fi
if [[ -e measurements/raw-lse.csv || -e measurements/raw-llsc.csv ]]; then
  echo 'Existing raw results; copy sources to a new directory to rerun.' >&2; exit 1
fi
for cmd in "$CXX" python3; do command -v "$cmd" >/dev/null; done
mkdir -p build measurements
python3 scripts/collect_env.py > measurements/environment.json
"$CXX" --version | head -n 1 > measurements/compiler-version.txt
common=(-std=c++17 -O3 -mtune=tsv110 -mno-outline-atomics -fno-lto -pthread -Wall -Wextra -Werror)
printf 'mode\tflags\n' > measurements/compiler-flags.tsv
for mode in lse llsc; do
  if [[ $mode == lse ]]; then arch=-march=armv8.2-a; else arch=-march=armv8-a; fi
  printf '%s\t%s\n' "$mode" "${common[*]} $arch" >> measurements/compiler-flags.tsv
  "$CXX" "${common[@]}" "$arch" -c src/counter.cpp -o "build/counter-$mode.o"
  "$CXX" "${common[@]}" "$arch" -S src/counter.cpp -o "measurements/counter-$mode.s"
  "$CXX" "${common[@]}" "$arch" src/bench.cpp "build/counter-$mode.o" -o "build/bench-$mode"
  "$CXX" -std=c++17 -O1 -g "$arch" -mtune=tsv110 -mno-outline-atomics -pthread \
    -fsanitize=undefined -fno-sanitize-recover=all -fno-lto -Wall -Wextra -Werror \
    src/bench.cpp src/counter.cpp -o "build/check-ubsan-$mode"
  "build/check-ubsan-$mode" --check-only --cpus "$CPUS" --controller "$CONTROLLER" \
    > "measurements/ubsan-$mode.stdout.txt" 2> "measurements/ubsan-$mode.stderr.txt"
done
date --iso-8601=seconds > measurements/timing-start.txt
for mode in lse llsc; do
  "build/bench-$mode" --cpus "$CPUS" --controller "$CONTROLLER" --rounds "$ROUNDS" --iterations "$ITERATIONS" \
    > "measurements/raw-$mode.csv" 2> "measurements/bench-$mode.stderr.txt"
done
date --iso-8601=seconds > measurements/timing-end.txt
sha256sum src/* scripts/run.sh scripts/collect_env.py > measurements/source-sha256.txt
python3 scripts/analyze.py

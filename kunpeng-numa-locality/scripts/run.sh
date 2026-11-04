#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export LC_ALL=C TZ=Asia/Shanghai
CC=${CC:-gcc}
export NUMACTL=${NUMACTL:-numactl}
for cmd in "$CC" python3 "$NUMACTL"; do command -v "$cmd" >/dev/null; done
if [[ $(uname -m) != aarch64 ]]; then echo 'AArch64 Linux required' >&2; exit 1; fi
if [[ -e measurements/raw.csv || -e measurements/job-0.stdout.txt ]]; then echo 'Existing results; use a new directory.' >&2; exit 1; fi
mkdir -p build measurements
python3 scripts/collect_env.py > measurements/environment.json
"$CC" --version | head -n 1 > measurements/compiler-version.txt
"$NUMACTL" --version > measurements/numactl-version.txt
flags=(-std=c11 -O3 -march=armv8-a -mtune=tsv110 -fno-lto -Wall -Wextra -Werror)
printf '%s\n' "${flags[*]}" > measurements/compiler-flags.txt
"$CC" "${flags[@]}" -c src/kernels.c -o build/kernels.o
"$CC" "${flags[@]}" -S src/kernels.c -o measurements/kernels.s
"$CC" "${flags[@]}" src/bench.c build/kernels.o -o build/bench
# Independent small working-set correctness/page-placement check, never timed for results.
"$CC" -std=c11 -O1 -g -march=armv8-a -mtune=tsv110 -fno-lto -Wall -Wextra -Werror \
  -fsanitize=undefined -fno-sanitize-recover=all src/bench.c src/kernels.c -o build/check-ubsan
"$NUMACTL" --physcpubind=4 --membind=0 build/check-ubsan 4 0 1 1 \
  > measurements/ubsan.stdout.txt 2> measurements/ubsan.stderr.txt
python3 scripts/run.py
sha256sum src/* scripts/run.sh scripts/run.py scripts/collect_env.py > measurements/source-sha256.txt

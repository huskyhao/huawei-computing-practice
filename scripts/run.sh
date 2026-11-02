#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export LC_ALL=C
export TZ=Asia/Shanghai
CC=${CC:-gcc}
CPU=${CPU:-4}
ROUNDS=${ROUNDS:-11}
TARGET_SECONDS=${TARGET_SECONDS:-0.2}
if [[ $(uname -m) != aarch64 ]]; then
  echo 'This experiment requires an AArch64 host with NEON.' >&2
  exit 1
fi
for command in "$CC" taskset python3; do command -v "$command" >/dev/null; done
if [[ -e measurements/raw.csv ]]; then
  echo 'measurements/raw.csv exists; copy this project to a new directory before rerunning.' >&2
  exit 1
fi
mkdir -p build measurements
{
  date --iso-8601=seconds
  uname -srvmo
  cat /etc/os-release
  lscpu
  "$CC" --version
  python3 --version
  printf '\nRUN CPU=%s ROUNDS=%s TARGET_SECONDS=%s\n' "$CPU" "$ROUNDS" "$TARGET_SECONDS"
  printf '\nInitial uptime and memory\n'
  uptime
  free -h
  printf '\nTHP policy\n'
  cat /sys/kernel/mm/transparent_hugepage/enabled
  printf '\nNUMA balancing\n'
  cat /proc/sys/kernel/numa_balancing
  printf '\nCPU cache topology\n'
  for dir in /sys/devices/system/cpu/cpu"$CPU"/cache/index*; do
    printf '%s ' "$(basename "$dir")"
    cat "$dir"/level "$dir"/type "$dir"/size "$dir"/coherency_line_size "$dir"/shared_cpu_list
  done
  printf '\nCPU governor/frequency (if exposed)\n'
  for file in /sys/devices/system/cpu/cpu"$CPU"/cpufreq/scaling_governor /sys/devices/system/cpu/cpu"$CPU"/cpufreq/scaling_cur_freq; do
    if [[ -r $file ]]; then printf '%s: ' "$(basename "$file")"; cat "$file"; fi
  done
} > measurements/environment.txt 2>&1
common=(-std=c11 -Wall -Wextra -Werror -fno-lto -march=armv8-a)
printf 'variant\toptions\n' > measurements/compiler-flags.tsv
compile_plain() {
  local variant=$1 symbol=$2
  shift 2
  printf '%s\t%s\n' "$variant" "${common[*]} $* -DSUM_NAME=$symbol" >> measurements/compiler-flags.tsv
  "$CC" "${common[@]}" "$@" -DSUM_NAME="$symbol" \
    -fopt-info-vec-all="measurements/$variant.vectorization.txt" \
    -c src/sum_plain.c -o "build/$variant.o"
  "$CC" "${common[@]}" "$@" -DSUM_NAME="$symbol" \
    -S src/sum_plain.c -o "measurements/$variant.s"
}
compile_plain scalar sum_scalar -O3 -mtune=generic -fno-tree-vectorize
compile_plain auto_o2 sum_o2 -O2 -mtune=generic
compile_plain auto_o3 sum_o3 -O3 -mtune=generic
compile_plain auto_tuned sum_tuned -O3 -mtune=tsv110
printf 'neon4\t%s\n' "${common[*]} -O3 -mtune=tsv110 (intrinsics)" >> measurements/compiler-flags.tsv
"$CC" "${common[@]}" -O3 -mtune=tsv110 -c src/sum_neon.c -o build/neon4.o
"$CC" "${common[@]}" -O3 -mtune=tsv110 -S src/sum_neon.c -o measurements/neon4.s
"$CC" "${common[@]}" -O2 src/bench.c build/*.o -o build/bench
# Sanitized correctness run is separate from the optimized timing run.
"$CC" "${common[@]}" -O1 -g -fsanitize=undefined -fno-sanitize-recover=all \
  -DSUM_NAME=sum_scalar -c src/sum_plain.c -o build/checked-scalar.tmp
"$CC" "${common[@]}" -O1 -g -fsanitize=undefined -fno-sanitize-recover=all \
  -c src/sum_neon.c -o build/checked-neon.tmp
"$CC" "${common[@]}" -O1 -g -fsanitize=undefined -fno-sanitize-recover=all \
  src/bench.c -x none build/checked-scalar.tmp build/checked-neon.tmp \
  build/auto_o2.o build/auto_o3.o build/auto_tuned.o -o build/check-ubsan
build/check-ubsan --check-only > measurements/ubsan.stdout.txt 2> measurements/ubsan.stderr.txt
date --iso-8601=seconds > measurements/timing-start.txt
taskset -c "$CPU" build/bench "$ROUNDS" "$TARGET_SECONDS" \
  > measurements/raw.csv 2> measurements/bench.stderr.txt
date --iso-8601=seconds > measurements/timing-end.txt
uptime > measurements/uptime-after.txt
sha256sum src/* scripts/run.sh > measurements/source-sha256.txt
python3 scripts/analyze.py

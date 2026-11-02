#define _GNU_SOURCE
#include "sum.h"
#include <errno.h>
#include <inttypes.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum { VARIANTS = 5 };
static const char *names[VARIANTS] = {
    "scalar", "auto_o2", "auto_o3", "auto_tuned", "neon4"
};
static sum_fn funcs[VARIANTS] = {
    sum_scalar, sum_o2, sum_o3, sum_tuned, sum_neon4
};
static volatile uint64_t sink;
static uint32_t state = 0x9202026u;

static uint32_t next_u32(void) {
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

static double now(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &t) != 0) {
        perror("clock_gettime");
        exit(1);
    }
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

/* Volatile reference reads keep the independent oracle a scalar operation. */
static uint64_t reference(const uint32_t *a, size_t n) {
    const volatile uint32_t *p = a;
    uint64_t sum = 0;
    for (size_t i = 0; i < n; ++i)
        sum += p[i];
    return sum;
}

static void require_equal(uint64_t actual, uint64_t expected,
                          const char *name, size_t n) {
    if (actual != expected) {
        fprintf(stderr, "FAIL %s n=%zu actual=%" PRIu64
                " expected=%" PRIu64 "\n", name, n, actual, expected);
        exit(2);
    }
}

static void selftest(void) {
    uint32_t a[264];
    unsigned checks = 0;
    for (int pattern = 0; pattern < 3; ++pattern) {
        for (size_t j = 0; j < 264; ++j)
            a[j] = pattern == 0 ? next_u32() :
                   pattern == 1 ? UINT32_MAX : (j & 1 ? 0 : UINT32_MAX);
        for (size_t offset = 0; offset < 4; ++offset)
            for (size_t n = 0; n <= 257; ++n) {
                uint64_t expected = reference(a + offset, n);
                for (int v = 0; v < VARIANTS; ++v) {
                    require_equal(funcs[v](a + offset, n), expected, names[v], n);
                    ++checks;
                }
            }
    }
    fprintf(stderr, "SELFTEST PASS checks=%u patterns=3 lengths=0..257 offsets=0..3\n", checks);
}

static double batch(sum_fn f, const uint32_t *a, size_t n,
                    size_t reps, uint64_t expected) {
    uint64_t checksum = 0;
    double start = now();
    for (size_t r = 0; r < reps; ++r)
        checksum += f(a, n);
    double elapsed = now() - start;
    sink = checksum;
    require_equal(checksum, expected * (uint64_t)reps, "batch checksum", n);
    return elapsed;
}

int main(int argc, char **argv) {
    selftest();
    if (argc == 2 && strcmp(argv[1], "--check-only") == 0)
        return 0;
    int rounds = argc > 1 ? atoi(argv[1]) : 11;
    double target = argc > 2 ? atof(argv[2]) : 0.2;
    if (rounds < 3 || rounds > 101 || target < 0.05 || target > 2.0) {
        fprintf(stderr, "Usage: bench [rounds:3..101] [target_seconds:0.05..2]\n");
        return 1;
    }
    cpu_set_t mask;
    if (sched_getaffinity(0, sizeof(mask), &mask) != 0 || CPU_COUNT(&mask) != 1) {
        fprintf(stderr, "Pin to one allowed CPU first: taskset -c CPU ./build/bench\n");
        return 1;
    }
    fprintf(stderr, "BENCH cpu=%d affinity_count=%d rounds=%d target_seconds=%.3f\n",
            sched_getcpu(), CPU_COUNT(&mask), rounds, target);
    puts("bytes,elements,round,order,variant,reps,elapsed_s,ns_per_scan,logical_gib_s,expected_sum,cpu_start,cpu_end");
    const size_t sizes[] = {256 * 1024, 256 * 1024 * 1024};
    for (size_t size_index = 0; size_index < 2; ++size_index) {
        size_t bytes = sizes[size_index], n = bytes / sizeof(uint32_t);
        uint32_t *a = NULL;
        int rc = posix_memalign((void **)&a, 128, bytes);
        if (rc != 0) { errno = rc; perror("posix_memalign"); return 1; }
        /* Allocation and first-touch initialization happen after CPU binding. */
        for (size_t i = 0; i < n; ++i)
            a[i] = next_u32();
        uint64_t expected = reference(a, n);
        size_t reps[VARIANTS];
        for (int v = 0; v < VARIANTS; ++v) {
            require_equal(funcs[v](a, n), expected, names[v], n);
            /* One full untimed warmup scan per implementation, then calibrate. */
            sink = funcs[v](a, n);
            size_t probe = 1;
            double elapsed;
            while ((elapsed = batch(funcs[v], a, n, probe, expected)) < 0.03)
                probe *= 2;
            reps[v] = (size_t)((double)probe * target / elapsed);
            if (reps[v] < 1) reps[v] = 1;
            fprintf(stderr, "CALIBRATE bytes=%zu variant=%s reps=%zu\n", bytes, names[v], reps[v]);
        }
        for (int round = 0; round < rounds; ++round) {
            int order[VARIANTS] = {0, 1, 2, 3, 4};
            for (int i = VARIANTS - 1; i > 0; --i) {
                int j = (int)(next_u32() % (uint32_t)(i + 1));
                int tmp = order[i]; order[i] = order[j]; order[j] = tmp;
            }
            for (int position = 0; position < VARIANTS; ++position) {
                int v = order[position];
                sink = funcs[v](a, n);
                int cpu_start = sched_getcpu();
                double elapsed = batch(funcs[v], a, n, reps[v], expected);
                int cpu_end = sched_getcpu();
                double ns = elapsed * 1e9 / (double)reps[v];
                double gib = (double)bytes * (double)reps[v] / elapsed / 1073741824.0;
                printf("%zu,%zu,%d,%d,%s,%zu,%.9f,%.6f,%.6f,%" PRIu64 ",%d,%d\n",
                       bytes, n, round, position, names[v], reps[v], elapsed,
                       ns, gib, expected, cpu_start, cpu_end);
                fflush(stdout);
            }
        }
        free(a);
    }
    fprintf(stderr, "BENCH PASS large_array_checks=10 batch_checks=all\n");
    return 0;
}

#include "counter.h"
#include <algorithm>
#include <cerrno>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <limits>
#include <new>
#include <pthread.h>
#include <random>
#include <sched.h>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <time.h>
#include <vector>

using Counter = std::atomic<std::uint64_t>;
static_assert(sizeof(Counter) == 8, "The tested layouts require 8-byte atomics");
static_assert(Counter::is_always_lock_free, "A lock-free uint64 atomic is required");

struct Layout { const char *name; std::size_t stride; };
const Layout layouts[] = {{"shared", 0}, {"packed8", 8}, {"stride64", 64},
                          {"stride128", 128}, {"stride256", 256}};

struct alignas(256) WorkerTimes {
    std::uint64_t start = 0, end = 0;
    int cpu_start = -1, cpu_end = -1;
};
struct Sample {
    std::uint64_t elapsed, skew, thread_min, thread_max, actual;
};

std::uint64_t now_ns() {
    timespec t{};
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &t))
        throw std::runtime_error("clock_gettime failed");
    return std::uint64_t(t.tv_sec) * 1000000000ULL + std::uint64_t(t.tv_nsec);
}

void pin(int cpu) {
    cpu_set_t mask;
    CPU_ZERO(&mask); CPU_SET(cpu, &mask);
    if (pthread_setaffinity_np(pthread_self(), sizeof(mask), &mask))
        throw std::runtime_error("pthread_setaffinity_np failed");
}

void barrier(pthread_barrier_t *b) {
    int rc = pthread_barrier_wait(b);
    if (rc && rc != PTHREAD_BARRIER_SERIAL_THREAD)
        throw std::runtime_error("pthread_barrier_wait failed");
}

Sample sample(const Layout &layout, const std::vector<int> &cpus,
              int count, std::uint64_t iterations) {
    const int slots = layout.stride ? count : 1;
    const std::size_t step = layout.stride ? layout.stride : sizeof(Counter);
    // Reuse one isolated page across EVERY layout, including single-thread cases.
    // This removes allocator size classes and changing base addresses as factors.
    alignas(4096) static unsigned char storage[4096];
    if (step * std::size_t(slots) > sizeof(storage) ||
        reinterpret_cast<std::uintptr_t>(storage) % 4096)
        throw std::runtime_error("unexpected storage alignment");
    std::vector<Counter *> counters;
    for (int i = 0; i < slots; ++i)
        counters.push_back(new (storage + step * std::size_t(i)) Counter(0));
    if (!counters.front()->is_lock_free())
        throw std::runtime_error("atomic implementation is not lock-free");
    std::vector<WorkerTimes> times(static_cast<std::size_t>(count));
    pthread_barrier_t gate;
    if (pthread_barrier_init(&gate, nullptr, unsigned(count + 1)))
        throw std::runtime_error("pthread_barrier_init failed");
    std::vector<std::thread> workers;
    for (int i = 0; i < count; ++i) {
        workers.emplace_back([&, i] {
            pin(cpus[std::size_t(i)]);
            Counter *target = counters[layout.stride ? std::size_t(i) : 0];
            // All counters are zero; the load touches the actual target untimed.
            if (target->load(std::memory_order_relaxed) != 0)
                std::abort();
            barrier(&gate);
            times[std::size_t(i)].cpu_start = sched_getcpu();
            times[std::size_t(i)].start = now_ns();
            increment_counter(target, iterations);
            times[std::size_t(i)].end = now_ns();
            times[std::size_t(i)].cpu_end = sched_getcpu();
        });
    }
    barrier(&gate);
    for (auto &worker : workers) worker.join();
    pthread_barrier_destroy(&gate);
    std::uint64_t total = 0;
    for (int i = 0; i < slots; ++i) {
        auto actual = counters[std::size_t(i)]->load(std::memory_order_relaxed);
        auto expected = layout.stride ? iterations : iterations * std::uint64_t(count);
        if (actual != expected) throw std::runtime_error("counter validation failed");
        total += actual;
        counters[std::size_t(i)]->~Counter();
    }
    auto begin = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t end = 0, last_begin = 0, minimum = begin, maximum = 0;
    for (int i = 0; i < count; ++i) {
        auto &t = times[std::size_t(i)];
        if (t.cpu_start != cpus[std::size_t(i)] || t.cpu_end != cpus[std::size_t(i)])
            throw std::runtime_error("worker CPU verification failed");
        begin = std::min(begin, t.start); end = std::max(end, t.end);
        last_begin = std::max(last_begin, t.start);
        minimum = std::min(minimum, t.end - t.start);
        maximum = std::max(maximum, t.end - t.start);
    }
    return {end - begin, last_begin - begin, minimum, maximum, total};
}

std::vector<int> parse_cpus(const std::string &value) {
    std::vector<int> result;
    std::istringstream stream(value);
    std::string token;
    while (std::getline(stream, token, ',')) {
        std::size_t consumed = 0;
        int cpu = std::stoi(token, &consumed);
        if (consumed != token.size() || cpu < 0 || cpu >= CPU_SETSIZE)
            throw std::runtime_error("invalid CPU identifier");
        result.push_back(cpu);
    }
    return result;
}

int main(int argc, char **argv) try {
    std::vector<int> cpus = {4, 5, 6, 7, 8, 9, 10, 11};
    int controller = 12, rounds = 9;
    std::uint64_t iterations = 2000000;
    bool check_only = false;
    for (int i = 1; i < argc; ++i) {
        std::string key = argv[i];
        if (key == "--check-only") { check_only = true; continue; }
        if (++i >= argc) throw std::runtime_error("missing option value");
        if (key == "--cpus") cpus = parse_cpus(argv[i]);
        else if (key == "--controller") controller = std::stoi(argv[i]);
        else if (key == "--rounds") rounds = std::stoi(argv[i]);
        else if (key == "--iterations") iterations = std::stoull(argv[i]);
        else throw std::runtime_error("unknown option");
    }
    if (cpus.size() != 8 || rounds < 3 || rounds > 101 ||
        iterations < 1 || iterations > 100000000 || controller < 0 || controller >= CPU_SETSIZE)
        throw std::runtime_error("require 8 worker CPUs, 3..101 rounds, 1..100000000 iterations");
    cpu_set_t allowed;
    if (sched_getaffinity(0, sizeof(allowed), &allowed))
        throw std::runtime_error("sched_getaffinity failed");
    std::vector<int> all = cpus; all.push_back(controller);
    std::sort(all.begin(), all.end());
    if (std::adjacent_find(all.begin(), all.end()) != all.end())
        throw std::runtime_error("worker and controller CPUs must be distinct");
    for (int cpu : all)
        if (!CPU_ISSET(cpu, &allowed)) throw std::runtime_error("CPU not allowed");
    pin(controller);
    int checks = 0;
    for (auto n : {0ULL, 1ULL, 31ULL})
        for (auto &layout : layouts)
            for (int threads : {1, 2, 4, 8}) {
                auto checked = sample(layout, cpus, threads, n);
                if (checked.actual != n * std::uint64_t(threads))
                    throw std::runtime_error("selftest total mismatch");
                ++checks;
            }
    std::cerr << "SELFTEST PASS cases=" << checks << " iterations=0,1,31 layouts=5 threads=1,2,4,8\n";
    if (check_only) return 0;
    std::cerr << "BENCH rounds=" << rounds << " iterations_per_worker=" << iterations
              << " controller_cpu=" << controller << " worker_cpus=";
    for (auto cpu : cpus) std::cerr << cpu << ';';
    std::cerr << " seed=9568341\n";
    struct Case { int layout; int threads; };
    std::vector<Case> cases;
    for (int l = 0; l < 5; ++l)
        for (int threads : {1, 2, 4, 8}) cases.push_back({l, threads});
    for (auto c : cases) sample(layouts[c.layout], cpus, c.threads, 50000);
    std::mt19937 random(9568341);
    std::cout << "round,order,threads,layout,stride_bytes,base_alignment,iterations_per_worker,total_ops,elapsed_ns,total_mops,start_skew_ns,min_thread_ns,max_thread_ns,actual_sum,worker_cpus,distinct_128b_regions\n";
    for (int round = 0; round < rounds; ++round) {
        std::shuffle(cases.begin(), cases.end(), random);
        for (std::size_t position = 0; position < cases.size(); ++position) {
            auto c = cases[position]; auto &layout = layouts[c.layout];
            auto s = sample(layout, cpus, c.threads, iterations);
            auto operations = iterations * std::uint64_t(c.threads);
            double mops = double(operations) * 1000.0 / double(s.elapsed);
            auto regions = layout.stride ? (layout.stride < 128 ?
                (layout.stride * std::size_t(c.threads - 1)) / 128 + 1 : std::size_t(c.threads)) : 1;
            std::cout << round << ',' << position << ',' << c.threads << ',' << layout.name << ','
                      << layout.stride << ",4096," << iterations << ',' << operations << ',' << s.elapsed
                      << ',' << mops << ',' << s.skew << ',' << s.thread_min << ',' << s.thread_max
                      << ',' << s.actual << ',';
            for (int i = 0; i < c.threads; ++i) {
                if (i) std::cout << ';';
                std::cout << cpus[std::size_t(i)];
            }
            std::cout << ',' << regions << '\n' << std::flush;
        }
        std::cerr << "ROUND " << round << " PASS\n";
    }
    std::cerr << "BENCH PASS samples=" << rounds * 20 << " all_counters_and_cpu_checks=pass\n";
    return 0;
} catch (const std::exception &e) {
    std::cerr << "ERROR: " << e.what() << '\n';
    return 1;
}

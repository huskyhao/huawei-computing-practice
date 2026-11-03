#include "counter.h"

extern "C" void increment_counter(std::atomic<std::uint64_t> *counter,
                                  std::uint64_t iterations) {
    for (std::uint64_t i = 0; i < iterations; ++i)
        counter->fetch_add(1, std::memory_order_relaxed);
}

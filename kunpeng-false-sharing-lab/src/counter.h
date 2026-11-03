#pragma once
#include <atomic>
#include <cstdint>
extern "C" void increment_counter(std::atomic<std::uint64_t> *counter,
                                  std::uint64_t iterations);

#pragma once
#include <stddef.h>
#include <stdint.h>
uint64_t scan_sum(const uint64_t *data, size_t words);
uint64_t chase_cycle(const uint64_t *data, size_t steps);

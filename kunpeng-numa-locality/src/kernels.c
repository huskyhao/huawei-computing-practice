#include "kernels.h"

uint64_t scan_sum(const uint64_t *data, size_t words) {
    uint64_t sum = 0;
    for (size_t i = 0; i < words; ++i) sum += data[i];
    return sum;
}

uint64_t chase_cycle(const uint64_t *data, size_t steps) {
    uint64_t index = 0;
    for (size_t i = 0; i < steps; ++i) index = data[index * 16];
    return index;
}

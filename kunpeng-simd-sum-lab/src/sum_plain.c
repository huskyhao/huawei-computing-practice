#include "sum.h"
#ifndef SUM_NAME
#error Define SUM_NAME when compiling this translation unit
#endif

uint64_t SUM_NAME(const uint32_t *a, size_t n) {
    uint64_t sum = 0;
    for (size_t i = 0; i < n; ++i)
        sum += a[i];
    return sum;
}

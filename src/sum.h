#ifndef KUNPENG_SUM_H
#define KUNPENG_SUM_H
#include <stddef.h>
#include <stdint.h>
typedef uint64_t (*sum_fn)(const uint32_t *, size_t);
uint64_t sum_scalar(const uint32_t *, size_t);
uint64_t sum_o2(const uint32_t *, size_t);
uint64_t sum_o3(const uint32_t *, size_t);
uint64_t sum_tuned(const uint32_t *, size_t);
uint64_t sum_neon4(const uint32_t *, size_t);
#endif

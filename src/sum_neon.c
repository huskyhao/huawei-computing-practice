#include "sum.h"
#include <arm_neon.h>

uint64_t sum_neon4(const uint32_t *a, size_t n) {
    uint64x2_t s0 = vdupq_n_u64(0), s1 = vdupq_n_u64(0);
    uint64x2_t s2 = vdupq_n_u64(0), s3 = vdupq_n_u64(0);
    size_t i = 0;
    for (; n - i >= 16; i += 16) {
        s0 = vpadalq_u32(s0, vld1q_u32(a + i));
        s1 = vpadalq_u32(s1, vld1q_u32(a + i + 4));
        s2 = vpadalq_u32(s2, vld1q_u32(a + i + 8));
        s3 = vpadalq_u32(s3, vld1q_u32(a + i + 12));
    }
    uint64_t sum = vaddvq_u64(vaddq_u64(vaddq_u64(s0, s1),
                                      vaddq_u64(s2, s3)));
    for (; i < n; ++i)
        sum += a[i];
    return sum;
}

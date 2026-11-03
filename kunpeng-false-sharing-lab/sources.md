# 官方资料与证据范围

核查日期：2026-11-02（Asia/Shanghai）。性能数值全部来自本项目服务器实测。

1. [鲲鹏社区：CacheLine 优化](https://www.hikunpeng.com/document/detail/zh/perftuning/tuningtip/kunpengtuning_12_0052.html)
   - 伪共享、内存对齐与填充的选题依据，以及鲲鹏 920 L3 128 字节 CacheLine 的说明。
   - 本机各级缓存行大小另由 sysfs 实测采集，不将 L3 字段直接等同于全部缓存或原子操作的粒度。
2. [Linux 内核文档：False Sharing](https://kernel.org/doc/html/latest/kernel-hacking/false-sharing.html)
   - 不同变量共享缓存行时的写入争用、布局优化与空间开销，以及 `perf c2c` 的分析方向。
   - 本项目没有执行 `perf c2c`，不把文档中的分析示例当作本次计数器证据。
3. [GCC 14.3：AArch64 Options](https://gcc.gnu.org/onlinedocs/gcc-14.3.0/gcc/AArch64-Options.html)
   - `-march`、`-mtune`、LSE 特性和 `-mno-outline-atomics` 的语义。
   - 两个内核的实际输出另保存为 `measurements/counter-lse.s` 与 `counter-llsc.s`。
4. [C++ 工作草案：atomics.order](https://eel.is/c++draft/atomics.order)
   - relaxed 放松内存排序要求，但仍要求原子访问不可分割；不能由此推导不存在缓存一致性成本。

## 本次可以直接验证的事实

- 正式源码使用固定的 4 KiB 对齐独立存储，同一进程中所有布局复用同一地址，计数器间距为显式常量。
- 所有工作线程固定在 CPU 4–11 的前若干个核心，控制线程为 CPU 12；本机这些核心共享 L3 域。
- 两种热点循环来自同一个 C++ 文件；生成汇编分别为 `ldadd` 与 `ldxr/stxr` 重试循环。
- 360 条正式记录和 120 条复核记录全部验证总计数与 CPU 位置，全部参与统计。
- 主程序和 UBSan 程序分别通过 60 种边界组合；复核程序复用正式二进制，另执行同样自检。

## 解释和限制

紧凑布局与分离布局的吞吐差异支持“热点计数器的共享布局显著影响扩展性”的判断；原子实现、缓存状态、调度和硬件细节对 LSE 波动的贡献没有被分解。未采集一致性流量、独占存储失败次数、CPU 周期或频率轨迹，因此不作精确的微观归因。详见 [正文](blog.md)与[公开版说明](PUBLICATION.md)。

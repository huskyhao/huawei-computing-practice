# 官方参考资料与证据范围

核查日期：2026-11-02（Asia/Shanghai）。文章为本次服务器实验的原创记录。

1. [鲲鹏社区：编译器调优手段](https://www.hikunpeng.com/document/detail/zh/perftuning/progtuneg/kunpengprogramming_05_0033.html)
   - 支持针对 `tsv110` 调优、通过编译器报告和优化参数开展实验的选题依据。
   - 使用其中 `-mtune=tsv110 -march=armv8-a` 的示例，没有将历史文档中的编译器版本称为当前最新版本。
2. [GCC 14.3：AArch64 Options](https://gcc.gnu.org/onlinedocs/gcc-14.3.0/gcc/AArch64-Options.html)
   - `-march` 控制可生成的目标指令，`-mtune` 控制针对处理器的性能调优；`tsv110` 是支持值。
3. [GCC 14.3：Optimize Options](https://gcc.gnu.org/onlinedocs/gcc-14.3.0/gcc/Optimize-Options.html)
   - `-O2` / `-O3` 的向量化与成本模型；具体生效状态另在真实服务器查询并记录于 `measurements/toolchain.txt`。
4. [Arm Neon Intrinsics Reference](https://arm-software.github.io/acle/neon_intrinsics/advsimd.html)
   - 核查 `vld1q_u32`、`vpadalq_u32`、`vaddq_u64`、`vaddvq_u64` 的语义；其中 `vpadalq_u32` 映射为 `UADALP`。


## 可以由现有证据直接支持的结论

- 系统和 CPU 拓扑来自 `environment.txt`；计时固定在 CPU 4，见 `bench.stderr.txt` 和 CSV 的 CPU 字段。
- O2 本循环没有向量化，O3 两种配置有 16 字节向量化，来自各自 `*.vectorization.txt`。
- 手写循环存在四条不同目标寄存器的 `uadalp`，来自 `neon4.s`。
- 所有结果均由未经筛选的 110 条批次记录计算；每条是多次扫描的平均时间。
- 实测源码与执行脚本的身份来自 `source-sha256.txt`；它在服务端实测后生成。
- 边界检查、全尺寸校验和批次校验全部通过；UBSan 额外覆盖框架、标量与手写 NEON 的插桩版本，三个自动编译版本使用原优化对象文件。

## 推断与未验证部分

- 四路累加缩短依赖链、大工作集更容易受访存影响，是结合汇编和结果作出的解释；没有逐项消融实验或 PMU 计数器来精确分解各项收益。
- CPU 先绑定再初始化有利于 first touch 放置，但没有显式 `membind`，也没有逐页核查 NUMA 位置；系统自动 NUMA balancing 为开启状态。
- 没有锁定 CPU 频率、进行长时间负载测试、测量多核扩展，也没有进行 x86 对照；不据此推导整机或跨架构性能结论。

## 公开版处理

环境日志经过脱敏摘录，工具链记录移除了机器专用路径；源码、110 条原始计时、汇编和正确性日志保持实测版本。详见 [PUBLICATION.md](PUBLICATION.md)。

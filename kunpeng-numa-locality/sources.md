# 官方资料与实验依据

核查日期：2026-11-04（Asia/Shanghai）。全部性能数值来自本次服务器实验。

1. [鲲鹏社区：NUMA 优化，减少跨 NUMA 访问内存](https://www.hikunpeng.com/document/detail/zh/perftuning/tuningtip/kunpengtuning_12_0014.html)
   - 支持本地与远端访存、CPU 亲和性的选题依据。本文没有采用文档中的预期收益作为本机实测值。
2. [Linux 内核文档：NUMA Memory Policy](https://docs.kernel.org/admin-guide/mm/numa_memory_policy.html)
   - CPU 调度约束与内存策略是不同层面的控制；任务策略影响后续分配，已有页不会仅因策略改变就自动迁移。
3. [numactl 项目：命令手册](https://github.com/numactl/numactl/blob/master/numactl.8)
   - `--physcpubind`、`--membind` 和 `--hardware` 的使用语义。
4. [Linux man-pages：move_pages(2)](https://man7.org/linux/man-pages/man2/move_pages.2.html)
   - `nodes=NULL` 时查询页面当前节点，不请求迁移；本项目设置 `pid=0, flags=0`，只查询自己的映射。

## 直接证据

- `environment.json` 保存节点 CPU 列表、相对 socket 分组、distance 矩阵与缓存信息。
- 每组进程的 CPU 位置、完整工作集校验、计时记录和前后页面分布可在 `job-*` 原始文件中核对。
- 全部 144 条样本和 16 次全页查询均参与自动复核；`raw.csv` 和 `placement.csv` 可从原始标准输出逐行重建。
- `kernels.s` 显示依赖地址链，以及顺序循环的 SIMD 累加。本次没有在不同节点使用不同的编译版本。

## 边界

依赖读取的 ns/跳包括地址计算、循环、TLB 和缓存层次等成本，不能视为纯 DRAM 器件延迟。顺序 GiB/s 是单个应用内核的逻辑输入吞吐，不能视为整机峰值或直接代替多线程 STREAM。没有锁频、独占 CPU、PMU、跨平台对照或真实业务测试。

页面在计时前后全部查询通过；没有在每一次读取之间查询，也不据此声称计时过程中记录了每一页的连续位置轨迹。系统自动 NUMA balancing 保留原设置，未做全局禁用。

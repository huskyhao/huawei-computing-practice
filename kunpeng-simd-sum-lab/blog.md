# 鲲鹏服务器 SIMD 优化实战：从 GCC 自动向量化到 NEON 四路累加

在鲲鹏服务器上编译一个 C 循环，打开 `-O3`、加入 `-mtune=tsv110`，再改成 NEON，这三步分别能带来多少收益？我用一个容易验证正确性的整数求和任务，在真实 TaiShan-v110 服务器上做了一组对照实验。

结果很有意思：256 KiB 数组上，GCC `-O3` 自动向量化相对标量基线加速约 **1.99 倍**，手写 NEON 四路累加达到 **5.53 倍**；把工作集扩大到 256 MiB，后者的加速比降为 **2.41 倍**。单独加入 `-mtune=tsv110` 的变化则很小，没有出现明显提升。

下面记录环境、实现、计时方法和汇编证据，看看这些数字是怎样得到的。

## 一、为什么选整数求和

扫描数组并累加，是统计聚合、数值预处理和数据分析中常见的计算模式。它的代码短，方便把编译器决策、指令选择和工作集大小分开观察。

任务定义为：输入 `uint32_t` 数组，输出 `uint64_t` 总和。本次最大输入为 67,108,864 个元素，即使所有元素都是 `UINT32_MAX`，数学结果也不会超过 64 位无符号整数上限。这样可以逐位比较结果，不需要讨论浮点误差，也不需要 `-ffast-math`。

普通 C 实现如下；实验将它以不同函数名、不同选项分别编译：

```c
uint64_t sum_plain(const uint32_t *a, size_t n) {
    uint64_t sum = 0;
    for (size_t i = 0; i < n; ++i)
        sum += a[i];
    return sum;
}
```

鲲鹏社区的[编译器调优文档](https://www.hikunpeng.com/document/detail/zh/perftuning/progtuneg/kunpengprogramming_05_0033.html)给出了 `-mtune=tsv110 -march=armv8-a` 的使用示例。我保留同一个 `-march=armv8-a`，只改变优化级别或 `-mtune`，以便观察具体是哪一步产生了变化。

## 二、真实运行环境

实验日期：2026 年 11 月 2 日，Asia/Shanghai。以下内容来自现场采集，而非服务器产品规格表。

| 项目 | 本次环境 |
|---|---|
| CPU 型号标识 | HiSilicon TaiShan-v110 |
| 架构 | AArch64，小端 |
| 拓扑 | 双路，每路 48 核，总计 96 个逻辑 CPU；每核 1 线程 |
| NUMA | 4 个节点，每节点 24 个 CPU |
| CPU 4 的缓存 | L1D 64 KiB、私有 L2 512 KiB；所在 L3 域 48 MiB，由 CPU 0–23 共享 |
| 内存 | 系统显示 188 GiB |
| 系统 | NixOS 26.05，Linux 6.12.111 |
| 编译器 | GCC 14.3.0，目标 `aarch64-unknown-linux-gnu` |
| 辅助工具 | Python 3.12.10、`taskset` |
| 运行配置 | 单线程，固定在 CPU 4 |

可以先用以下命令核查自己的机器：

```bash
uname -m
lscpu
gcc --version
python3 --version
grep Cpus_allowed_list /proc/self/status
```

这台机器默认 PATH 中没有 GCC 和 Python。我复用了已经存在于 Nix store 的工具链，只在当前 shell 中调整 PATH；公开的版本与优化选项记录保存在 [toolchain.txt](measurements/toolchain.txt)，机器专用路径已移除。本实验没有修改系统配置，也不要求安装 CANN 或使用昇腾加速卡。

## 三、五种实现，只改一个明确的因素

各版本均使用 C11、相同输入、同一个计时程序，并明确关闭 LTO，分别编译为对象文件后链接。

| 名称 | 求和函数的关键选项 | 目的 |
|---|---|---|
| `scalar` | `-O3 -march=armv8-a -mtune=generic -fno-tree-vectorize` | 保留常规优化，显式关闭自动向量化，作为标量对照 |
| `auto_o2` | `-O2 -march=armv8-a -mtune=generic` | 观察 GCC O2 的实际决策 |
| `auto_o3` | `-O3 -march=armv8-a -mtune=generic` | 观察 O3 自动向量化 |
| `auto_tuned` | `-O3 -march=armv8-a -mtune=tsv110` | 只改变目标处理器调优 |
| `neon4` | `-O3 -march=armv8-a -mtune=tsv110`，使用 intrinsics | 显式使用四路 NEON 累加 |

这里的 5.53 倍对应“手写 NEON 与显式关闭向量化的 O3 基线”的比较。如果实际应用本来就使用 O3 自动向量化，还应该比较 `neon4` 与 `auto_o3`，不能直接套用 5.53 倍。

`-march` 允许生成相应架构的指令，`-mtune` 则影响针对目标处理器的调度与性能调优，二者的区别见 [GCC AArch64 官方说明](https://gcc.gnu.org/onlinedocs/gcc-14.3.0/gcc/AArch64-Options.html)。本次没有通过切换指令集来扩大 `auto_tuned` 的优势。

### NEON 实现：先拓宽，再累加

核心代码如下，完整文件为 [src/sum_neon.c](src/sum_neon.c)：

```c
#include <stddef.h>
#include <stdint.h>
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
```

`vld1q_u32` 一次读入 4 个 32 位元素；`vpadalq_u32` 将相邻的 32 位元素成对拓宽求和，再加入 64 位累加器。四个累加器让主循环每轮处理 16 个元素，最后统一归约。对应语义可以查阅 [Arm Neon Intrinsics Reference](https://arm-software.github.io/acle/neon_intrinsics/advsimd.html)。

需要注意类型：如果一直在 32 位向量中累加，数据较大时就可能先溢出，再转成 64 位也无法恢复。这里从累加阶段就使用 64 位 lane。尾部不足 16 个元素时，由普通循环处理。

## 四、先检查正确性，再计时

测试框架使用独立的、通过 `volatile` 逐项读取的参考求和函数，检查以下组合：

- 长度从 0 到 257，覆盖空数组及不同尾部长度。
- 起始地址偏移 0、1、2、3 个 `uint32_t`，覆盖不同的 16 字节对齐情况。
- 数据模式包括固定种子的伪随机数、全部 `UINT32_MAX`、最大值与零交替。
- 每种组合分别调用五个版本。

合计 **15,480 项比较全部通过**。两种完整工作集还会分别校验五个版本，每个计时批次结束后检查累加校验和。

此外，我对测试框架、标量实现和手写 NEON 实现额外编译了 UBSan 插桩版本，单独运行边界检查，未发现运行时错误；三个自动编译版本在这次检查中仍使用原优化对象文件。插桩二进制没有用于正式性能计时。

日志保存在 [bench.stderr.txt](measurements/bench.stderr.txt) 和 [ubsan.stderr.txt](measurements/ubsan.stderr.txt)。

### 计时怎样避免常见干扰

我选择两个工作集：256 KiB 对应 65,536 个元素，小于 CPU 4 的 512 KiB 私有 L2；256 MiB 对应 67,108,864 个元素，超过所在 48 MiB L3 域容量。二者都在同一核心上反复扫描。

运行方式为：

```bash
taskset -c 4 build/bench 11 0.2
```

计时采用 `CLOCK_MONOTONIC_RAW`。数组分配、伪随机数生成、初始化和参考结果计算均在计时之外；进程在初始化之前就已经绑定到一个 CPU。每个版本先预热，再自动确定重复次数，目标批次时长约 0.2 秒，重复次数取整数。

正式测量分 11 轮，每轮以固定种子生成的随机顺序遍历五个版本。小数组每个批次扫描数千至数万次；大数组的标量版本每批 2 次，NEON 每批 7 次，因此不能把“目标 0.2 秒”理解为每一批严格等长。

循环通过函数指针调用单独编译的函数，关闭 LTO，并消费每次返回值。校验在批次计时结束后进行，防止计算结果被编译器当作无用代码消除。

最后得到 **2 种工作集 × 5 种实现 × 11 轮 = 110 条批次记录**，全部保留，没有筛除慢样本。每条记录是“多次扫描的总时间 / 扫描次数”，表中的中位数是 11 个批次均值的中位数，吞吐范围是这些批次的最小值到最大值，并非单次延迟分位数。

## 五、结果：小数组与大数组的收益不同

| 工作集 | 实现 | 中位耗时（µs/次） | 逻辑吞吐（GiB/s） | 吞吐范围 | 相对标量加速 |
|---|---|---:|---:|---:|---:|
| 256 KiB | `scalar` | 50.645 | 4.82 | 4.82–4.83 | 1.00× |
| 256 KiB | `auto_o2` | 50.653 | 4.82 | 4.81–4.83 | 1.00× |
| 256 KiB | `auto_o3` | 25.489 | 9.58 | 9.54–9.62 | 1.99× |
| 256 KiB | `auto_tuned` | 25.476 | 9.58 | 9.55–9.62 | 1.99× |
| 256 KiB | `neon4` | 9.157 | 26.66 | 26.62–26.74 | 5.53× |
| 256 MiB | `scalar` | 69583.985 | 3.59 | 3.57–3.62 | 1.00× |
| 256 MiB | `auto_o2` | 70061.595 | 3.57 | 3.41–3.63 | 0.99× |
| 256 MiB | `auto_o3` | 37942.024 | 6.59 | 6.54–6.60 | 1.83× |
| 256 MiB | `auto_tuned` | 37855.202 | 6.60 | 6.53–6.64 | 1.84× |
| 256 MiB | `neon4` | 28815.933 | 8.68 | 8.51–8.76 | 2.41× |

这里定义：

```text
逻辑吞吐 GiB/s = 数组字节数 × 扫描次数 / 批次秒数 / 2^30
相对标量加速比 = 标量的中位每次扫描耗时 / 当前实现的中位每次扫描耗时
```

逻辑吞吐统计的是程序扫描的输入字节数。缓存中的数据可以被反复读取，因此 26.66 GiB/s 不能当作 DRAM 带宽测量。表中的耗时统一使用微秒，例如 256 MiB 的 NEON 为约 28.82 毫秒。

![鲲鹏单核求和：五种实现与两种工作集的实测吞吐](assets/throughput.png)

图中两个面板使用相同横轴刻度；柱长表示中位数，散点为全部 11 个批次，括号内为相对标量加速比。

如果以 O3 自动向量化作为现有应用的起点，手写 NEON 在 256 KiB 工作集上进一步加速约 **2.78 倍**，在 256 MiB 上进一步加速约 **1.32 倍**。这是评估是否值得维护平台专用代码时更有参考意义的一组数字。

## 六、用报告和汇编解释结果

### O2 没有向量化，不能推广成“O2 不支持向量化”

本次 `auto_o2.vectorization.txt` 记录：

```text
missed: couldn't vectorize loop
missed: Loop costings not worthwhile.
```

而 O3 两种配置都记录：

```text
optimized: loop vectorized using 16 byte vectors
```

我又在现场查询了 `gcc -Q --help=optimizers`：O2 的循环向量化开关其实已经启用，成本模型为 `very-cheap`；O3 使用 `dynamic`。这与 [GCC 14.3 优化选项文档](https://gcc.gnu.org/onlinedocs/gcc-14.3.0/gcc/Optimize-Options.html)一致。`very-cheap` 对能否完全替代标量循环更保守，而这里的通用接口需要支持任意长度和尾部处理。

因此，准确结论是：**本次 GCC 14.3 对这段通用长度求和循环，在 O2 下选择了标量代码，在 O3 下选择了向量代码。** 是否成功向量化，应当看当前编译器的报告和输出。

### 自动向量化之后，仍然可能存在累加依赖

`auto_tuned.s` 的主循环包含：

```asm
ldr     q30, [x2], 16
uaddw   v31.2d, v31.2d, v30.2s
uaddw2  v31.2d, v31.2d, v30.4s
```

两次拓宽加法都更新 `v31`，后一次依赖前一次结果。手写 NEON 的主循环则出现：

```asm
ldp     q27, q28, [x2]
ldp     q29, q30, [x2, 32]
add     x2, x2, 64
uadalp  v31.2d, v27.4s
uadalp  v24.2d, v28.4s
uadalp  v25.2d, v29.4s
uadalp  v26.2d, v30.4s
```

这里使用不同目标寄存器，形成四条独立累加链，同时用成对拓宽累加指令和更大的循环步长处理数据。这些差异为小工作集上的额外收益提供了解释。

但这组实验同时改变了累加链、指令形式和循环展开程度，没有逐项消融，所以不能把全部提升精确归因于其中某一个因素。保存汇编的意义，是让解释有可以检查的依据。

### tsv110 参数为什么没有明显增益

256 KiB 下，`auto_o3` 与 `auto_tuned` 分别为 9.578 和 9.583 GiB/s；256 MiB 下分别为 6.589 和 6.604 GiB/s，差异都很小，且测量范围重叠。

对这个很短的循环，两个版本生成的向量主循环结构接近。`-mtune=tsv110` 没有自动把它改写成四路累加，因此这次不能据此宣称出现了明显的鲲鹏调优收益。该参数在其他程序上是否有效，仍应以相应负载的实测为准。

### 工作集变大后，为什么加速比缩小

手写 NEON 从小数组的 26.66 GiB/s 降到大数组的 8.68 GiB/s，对标量的加速比也从 5.53 倍降到 2.41 倍。小工作集能容纳在私有 L2，大工作集超过本地 L3 域，缓存层次与数据供给成本自然需要纳入分析。

这是根据工作集和吞吐变化作出的解释。本次没有采集 PMU 或内存控制器计数器，不能进一步断言“已经跑满内存带宽”，也不能量化每级缓存缺失的贡献。

## 七、怎样复现与继续使用

项目保留以下文件：

```text
kunpeng-simd-sum/
├── blog.md
├── README.md
├── sources.md
├── src/                  # 普通 C、NEON、测试与计时框架
├── scripts/              # 编译、分析、绘图、核查
├── measurements/         # 原始 CSV、汇总、环境、报告、汇编
└── assets/throughput.png
```

在准备好 GCC、Python 3 和 `taskset` 的 AArch64 Linux 上，将 `src/` 与 `scripts/` 放入一个新实验目录，然后运行：

```bash
CPU=4 ROUNDS=11 TARGET_SECONDS=0.2 bash scripts/run.sh
```

如果目录已经包含本次的 `measurements/raw.csv`，脚本会停止，避免覆盖原始证据。复制源码到新目录再重测的命令，以及 NixOS 的工具链准备说明，见 [README](README.md)。CPU 编号应根据自己的允许列表选择。

只想复算结果时，无需连接服务器：

```bash
python scripts/analyze.py
python scripts/verify_artifacts.py
```

如果本机装有 Matplotlib，还可以运行 `python scripts/make_figure.py` 重新生成配图。正式计时阶段从 16:49:45 开始，到 16:50:10 结束，约 25 秒，包含自检、初始化、预热、校准和测量；不包含此前的编译与独立 UBSan 检查。

## 八、这次实践带来的判断

在这个求和内核上，先查看编译器报告并使用 O3，已经能获得接近两倍的加速；进一步手写 NEON，收益与工作集大小有明显关系。对频繁扫描、缓存可容纳的小数组，四路拓宽累加值得进一步尝试；对更大的数组，应把实际访存表现一起纳入评估。

这次只使用一个固定核心，没有锁定 CPU 频率，没有显式绑定内存节点，也未逐页核查 NUMA 放置；系统自动 NUMA balancing 处于开启状态。实验未覆盖多核扩展、跨节点访问、长时间运行或 x86 对照，因此这些数字只描述当前机器、工具链与输入规模下的这个内核。

实际采用优化时，我会保留普通 C 路径，先在业务数据上验证正确性和端到端收益，再决定是否引入平台专用实现。鲲鹏调优最终要回答的，是具体程序的时间花在哪里，以及改动是否确实减少了那部分时间。

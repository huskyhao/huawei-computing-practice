# 鲲鹏多线程计数器：伪共享、缓存行填充与原子指令实测

**[技术博客正文](blog.md)** · **[官方参考资料](sources.md)** · **[公开版说明](PUBLICATION.md)**

2026-11-02，在真实 HiSilicon TaiShan-v110 / NixOS 26.05 / GCC 14.3.0 上完成实验。与 SIMD 求和实验不同，本项目研究多线程写入相邻计数器时的性能退化。

同一 L3 域内固定 1、2、4、8 个工作线程，比较共享单计数器和 8/64/128/256 字节间距，并分别生成 LSE 与 LL/SC 两种原子实现。

- 主实验：每线程 200 万次原子加，9 轮随机顺序，共 360 条记录。
- 加长复核：使用完全相同的二进制，每线程 800 万次，3 轮，共 120 条记录。
- 8 线程 LL/SC：紧凑布局 24.38 Mops/s，128 B 间距 1296.41 Mops/s，相对加速约 53.17 倍。
- 8 线程 LSE：相应中位吞吐 46.14 与 451.02 Mops/s；填充布局存在慢批次，加长复核后仍存在，正文保留范围并说明限制。

这是人工构造的高频原子计数器微基准，加速比不代表真实业务端到端收益。

![双原子模式与五种布局的线程扩展](assets/scaling.png)

## 复核已保存结果

只需要 Python 3，不需要鲲鹏硬件：

```bash
git clone https://github.com/huskyhao/kunpeng-false-sharing-lab.git
cd kunpeng-false-sharing-lab
python scripts/analyze.py
python scripts/verify_artifacts.py
```

所有性能统计使用 Python 标准库；绘图额外需要 Matplotlib：

```bash
python scripts/make_figure.py
```

## 在 AArch64 Linux 重新运行

准备 GCC、Python 3、pthread 支持。主机须支持 LSE（本次机器支持），GCC 必须识别 `-mtune=tsv110`。本次使用 GCC 14.3.0；其他版本应核查实际汇编。

复制源码与脚本到新目录，保留公开数据：

```bash
mkdir -p ../kunpeng-false-sharing-rerun
cp -r src scripts ../kunpeng-false-sharing-rerun/
cd ../kunpeng-false-sharing-rerun
CPUS=4,5,6,7,8,9,10,11 CONTROLLER=12 bash scripts/run.sh
bash scripts/validate_longer.sh
python3 scripts/analyze.py
```

`CPUS` 需要 8 个不同的允许 CPU，`CONTROLLER` 为另一个允许 CPU；先通过 `grep Cpus_allowed_list /proc/self/status` 和 `lscpu` 核查，并尽量选择同一 L3 域。修改 CPU 后，运行复核脚本时也应传入相同的 `CPUS` 和 `CONTROLLER`。程序会检查绑核结果和所有最终计数。

`run.sh` 可通过 `ROUNDS`、`ITERATIONS` 调整主实验。复核固定为每线程 800 万次、3 轮。脚本遇到已有原始 CSV 会停止，避免覆盖证据。NixOS 用户需自行将已准备的 GCC 和 Python 加入当前 shell PATH；仓库不依赖机器专用 store 路径。

## 文件说明

- `src/counter.cpp`：所有布局共用的原子加法内核。
- `src/bench.cpp`：固定内存基址、逐线程绑核、屏障、计时与正确性检查。
- `measurements/raw-lse.csv`、`raw-llsc.csv`：360 条原始主实验记录。
- `measurements/raw.csv`：分析脚本生成的合并视图，增加 `atomic_mode` 字段。
- `validation/`：120 条加长复核原始记录、日志与结果表。
- `measurements/environment.json`：通过白名单采集的实验环境与各级缓存拓扑。
- `measurements/counter-*.s`：确认实际使用 `ldadd` 或 `ldxr/stxr` 的汇编。
- `measurements/source-sha256.txt`、`validation/script-sha256.txt`：实测代码身份校验。
- `assets/scaling.png`：正文配图，发布文章时一并上传。

`verify_artifacts.py` 面向本仓库的完整交付，要求同时存在主实验、加长复核、正文与配图；复制源码重跑后可先使用 `analyze.py` 复核数值。

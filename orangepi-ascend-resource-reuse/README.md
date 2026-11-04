# 昇腾 310B：模型、Dataset 与 I/O 内存复用实验

[博客正文](blog.md) · [公开材料说明](PUBLICATION.md) · [官方资料](sources.md)

项目地址：[huawei-computing-practice / orangepi-ascend-resource-reuse](https://github.com/huskyhao/huawei-computing-practice/tree/main/orangepi-ascend-resource-reuse)

在 Orange Pi AIpro / Ascend310B1 / CANN 8.0.0 上，固定一个 batch=32 的数字分类 OM，比较四种同步推理资源生命周期。完成五轮共 24,000 条请求计时，并用十二个独立进程观察初始化与首批调用。输出与固定参考逐元素一致，四种策略测试集准确率均为 352/360。

| 策略 | 平均耗时 / 微秒 |
| --- | ---: |
| 模型、I/O 内存与 Dataset 全部复用 | 101.344 |
| 每次重建 Dataset 与 DataBuffer | 129.501 |
| 每次申请 I/O 内存并重建描述对象 | 184.399 |
| 每次加载模型、申请内存、推理并全部释放 | 10,442.549 |

每次调用包含 32 个输入槽位；计时包含输入复制、同步执行、输出数组复制与策略所需的资源操作，不含输入预处理、常驻资源准备或网络服务。性能比值适用于本次小模型和环境，不能当作纯算子加速倍数。

## 在普通电脑上复核

克隆合集并进入本实验目录，无需安装 CANN 或 NumPy：

```bash
git clone https://github.com/huskyhao/huawei-computing-practice.git
cd huawei-computing-practice/orangepi-ascend-resource-reuse
python scripts/analyze_results.py
python scripts/verify_artifacts.py
```

前者重新计算已保存统计值；后者校验发布文件哈希和 Markdown 相对链接。它们不重新推理，只复核保存的证据。

## 在开发板上重新实验

需要已有可用的 CANN 8.0.0 和匹配设备的 pyACL。本脚本仅验证并支持集成板的 `ACL_DEVICE=0` 模式，使用设备 0；不改系统 CANN，也不停止其他进程。

如果从零准备本实验输入：

```bash
bash scripts/setup.sh
bash scripts/rebuild_model.sh
```

`setup.sh` 创建本目录 `.venv` 并安装固定 Python 依赖；没有 ensurepip 时会下载 PyPA virtualenv。重建脚本用 sklearn 自带数据集训练同架构模型，导出 ONNX 后只转换 batch=32 OM，SoC 由设备查询。重建不是本次计时的一部分，也不保证跨工具版本的二进制哈希相同。

若已完成前一篇 ONNX→OM 实验，可复制现有模型与输入并使用已有虚拟环境：

```bash
BASELINE_DIR=/path/to/ascend310b-digits-onnx-om bash scripts/prepare_inputs.sh
export EXPERIMENT_VENV=/path/to/ascend310b-digits-onnx-om/.venv
```

当不设置 `EXPERIMENT_VENV` 时，运行脚本使用本目录的 `.venv`。正式命令：

```bash
bash scripts/collect_env.sh before
bash scripts/run.sh --label formal --rounds 5 --repeats 1200 --warmup 20
cp logs/latest-run.log logs/formal.log
bash scripts/run.sh --startup --processes 12
cp logs/latest-run.log logs/startup.log
bash scripts/collect_env.sh after
python scripts/analyze_results.py --base results --write
```

`results/` 保存本机重跑产生的完整数据；`measurements/` 是本次实测的可分享快照，重跑不会覆盖它。使用相同 label 再跑会覆盖 `results/` 中同名实验结果。日志和模型均在本目录生成。

## 文件用途

- `blog.md`：可以直接使用的技术博客正文，附计时范围、限制与官方资料链接。
- `scripts/resource_lab.py`：四种资源策略、逐请求计时与独立进程实验。
- `measurements/formal/requests.csv`：24,000 条正式计时。
- `measurements/formal/metadata.json`：配置、随机顺序、模型哈希与正确性断言的记录。
- `measurements/startup/processes.csv`：十二次进程实验。
- `measurements/summary.json`：由标准库脚本从 CSV 重新计算的汇总。
- `measurements/environment.json`：去除机器身份信息的环境事实。
- `assets/`：两张基于保存数据生成的图。

如需重新绘图，另安装 Matplotlib 和 NumPy，在本目录运行：

```bash
python -m pip install matplotlib numpy
python scripts/make_figures.py
# 对重跑结果绘图：
# python scripts/make_figures.py --base results
```

原始机器日志、模型、逐样本输出只在本地完整材料中保留。公开范围见 [PUBLICATION.md](PUBLICATION.md)。

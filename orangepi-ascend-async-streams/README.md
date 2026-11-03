# 昇腾 pyACL 异步推理与 Stream 实测

[返回合集目录](../README.md) · **[实验报告](report.md)** · [公开版说明](PUBLICATION.md)

2026-11-03，在 Orange Pi AIpro / Ascend310B1 / CANN 8.0.0 上，固定同一份 batch=32 数字分类模型，比较同步串行、异步逐次等待、单 Stream 分组等待和双 Stream 分组等待。

- 完成 32 个场景、19,200 个完成窗口的测量，含 408,000 次模型调用。
- W=64 时，单 Stream 分组等待的张量处理速率约为同步串行的 2.12 倍。
- 双 Stream 在该场景没有继续提速；四种策略在 360 条独立测试数据上均识别正确 352 条，logits 逐位一致。
- 保留同一模型实例先同步后异步产生 `NnExecute not support mix execute` 的最小复现。

这些数字对应本次小模型、软件版本和计时范围，完整条件及边界见报告。

## 在普通电脑上复核公开数值

需要 Python 和 NumPy，无须昇腾硬件：

```bash
git clone https://github.com/huskyhao/huawei-computing-practice.git
cd huawei-computing-practice/orangepi-ascend-async-streams
python scripts/verify_public_results.py
```

`measurements/` 包含正式汇总、全部数值计时、精简诊断结果和本地完整材料的核查记录。原始机器日志、进程 ID、模型文件和逐样本 NPZ 数组保留在本地。

## 在昇腾开发板上重新实验

在已安装匹配 CANN 的开发板上，从当前项目目录执行：

```bash
bash scripts/setup.sh
bash scripts/rebuild_model.sh
bash scripts/collect_env.sh
bash scripts/run.sh --warmup 20 --repeats 200 --rounds 3 --out-stem formal
```

依赖安装在本目录 `.venv` 中；训练与 ATC 在本机生成模型。脚本面向实测的 `ACL_DEVICE` 板端模式。`run.sh` 使用本目录的 `.venv`，也可以显式设置 `EXPERIMENT_VENV` 复用已有环境。`prepare_baseline.sh` 可通过 `BASELINE_DIR` 指向已经生成模型的项目目录。

重新运行会更新 `models/`、`results/` 和 `logs/`；这些目录默认不提交。保留原始证据时，先复制项目再重跑。

### 复现执行模式混用现象

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source .venv/bin/activate
python scripts/probe_async.py > logs/probe-explicit.log 2>&1
python scripts/probe_async.py --default-stream > logs/probe-default.log 2>&1
python scripts/probe_async.py --sync-first > logs/probe-sync-first-explicit.log 2>&1
python scripts/probe_async.py --sync-first --default-stream > logs/probe-sync-first-default.log 2>&1
```

每次程序输出 `PROBE_RESULT` 结构，预期失败会作为返回码记录。该现象的结论范围限定为报告中的 CANN 版本与模型，不推断其他版本必然相同。

## 分析自己重跑的完整结果

收回完整 `models/`、`results/`、`logs/` 后，在装有 NumPy 和 Matplotlib 的电脑上执行：

```bash
python scripts/analyze_results.py
python scripts/write_report.py
```

这些脚本会验证逐样本数组、输入哈希、全部窗口和四个探测对照，再生成配图与报告。公开数据的快速核对只需运行前述 `verify_public_results.py`。

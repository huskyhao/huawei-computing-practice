# 本次实验的公开数据

这些结果来自 2026-11-02 的 Orange Pi AIpro / Ascend310B1 / CANN 8.0.0 实机实验。

- `training.json`：训练设置、测试划分、准确率和 ONNX 参考计算检查。
- `benchmark.json`：三个 batch 的准确率、误差、延迟统计及线程池配置。
- `cpu-thread-check.json`：CPU 四线程异常的独立复核，含数值计时样本。
- `latency_samples.csv`：18,000 条数值延迟记录，可重算主文统计。
- `requirements-resolved.txt`：实际安装的 Python 包版本。

发布时仅移除了 JSON 中线程库的 `filepath` 字段；性能数值与原始记录一致。CSV 只包含 batch、场景、轮次、迭代编号和耗时，已逐行验证其类型与取值。

公开仓库不包含本机环境原始日志、ONNX/OM 模型文件、权重或逐样本 NPZ 数组。上述原始材料保留在本地；运行仓库中的训练、转换和推理脚本会在目标设备重新生成。`scripts/verify_artifacts.py` 用于核对重新生成的完整实验材料。

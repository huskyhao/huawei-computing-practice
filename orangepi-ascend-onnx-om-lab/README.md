# Orange Pi AIpro 昇腾推理实测

[返回合集目录](../README.md)

在 Orange Pi AIpro / Ascend310B1 / CANN 8.0.0 上完成手写数字分类模型的 ONNX → OM 转换、pyACL 推理和静态 batch 性能测试。

**[阅读完整技术博客](blog.md)** · **[官方参考资料](sources.md)**

三个 batch（1、32、128）在同一组 360 条测试数据上均识别正确 352 条，准确率为 97.78%，预测类别与 CPU 基线完全一致。项目保留了 18,000 条计时样本、CPU 多线程异常的复核以及设备告警等实验条件；详细计时范围与结果见正文。

- `blog.md`：技术博客正文。
- `assets/`：正文配图，来自真实结果。
- `scripts/`：环境采集、独立环境安装、训练与 ONNX 导出、ATC 转换、pyACL 验证与计时、绘图脚本。
- `measurements/`：移除本机路径后的训练和性能汇总、CPU 线程复核结果，以及 18,000 条数值延迟记录。
- `models/`、`results/`、`logs/`：运行脚本后在目标板生成，已加入 Git 忽略规则。本次原始环境日志、模型及逐样本数组保留在本地实验目录。
- `sources.md`：官方参考资料及核查范围。

实验日期：2026-11-02（Asia/Shanghai）。

## 在同类已安装 CANN 的板子上复现

在已安装 CANN 的开发板上克隆仓库，然后执行：

```bash
git clone https://github.com/huskyhao/huawei-computing-practice.git
cd huawei-computing-practice/orangepi-ascend-onnx-om-lab
bash scripts/collect_env.sh
bash scripts/setup.sh
bash scripts/run.sh
```

`setup.sh` 将依赖安装到 `.venv`。系统缺少 ensurepip 时，脚本从 PyPA 官方地址下载 virtualenv zipapp 完成引导。`convert.sh` 从实际设备读取 SoC 名称，不按主机名猜测芯片型号。

OM 文件由本次 Ascend310B1 / CANN 8.0.0 环境生成。其他芯片、工具链应在目标环境重新转换，不应假定该二进制通用。

完整重跑会重新生成模型、结果与日志；要保留本次证据，请先复制目录后再运行。

## 生成配图

在装有 NumPy 和 Matplotlib 的电脑上，对已回收结果执行：

```bash
python scripts/make_figures.py
python scripts/verify_artifacts.py
```

博客中的图使用 `assets/` 相对路径，在 GitHub 中可直接查看；发布到博客平台时需一起上传两张 PNG。

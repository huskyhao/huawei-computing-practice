# 鲲鹏与昇腾技术实践

统一整理鲲鹏服务器和昇腾开发板上的实机实验、技术博客、复现脚本与公开数值结果。后续实验继续新增子目录，统一在本仓库维护。

## 实验目录

| 平台 | 实验 | 正文 | 项目与复现 |
| --- | --- | --- | --- |
| 鲲鹏 TaiShan-v110 | GCC 自动向量化、NEON 与单核求和吞吐 | [技术博客](kunpeng-simd-sum-lab/blog.md) | [项目说明](kunpeng-simd-sum-lab/README.md) |
| 鲲鹏 TaiShan-v110 | 伪共享、缓存行填充、LSE 与 LL/SC 原子指令 | [技术博客](kunpeng-false-sharing-lab/blog.md) | [项目说明](kunpeng-false-sharing-lab/README.md) |
| 昇腾 Ascend310B1 / Orange Pi AIpro | ONNX 转 OM、pyACL 数字分类与静态 batch 测试 | [技术博客](orangepi-ascend-onnx-om-lab/blog.md) | [项目说明](orangepi-ascend-onnx-om-lab/README.md) |
| 昇腾 Ascend310B1 / Orange Pi AIpro | 同步/异步推理、分组等待与双 Stream | [实验报告](orangepi-ascend-async-streams/report.md) | [项目说明](orangepi-ascend-async-streams/README.md) |

这些结果来自具体软硬件和受控微基准，各篇正文记录了计时范围、异常结果与适用边界。

## 仓库结构

```text
huawei-computing-practice/
├── README.md
├── kunpeng-simd-sum-lab/
├── kunpeng-false-sharing-lab/
├── orangepi-ascend-onnx-om-lab/
└── orangepi-ascend-async-streams/
```

各项目都是普通目录，一次克隆即可获取完整公开内容：

```bash
git clone https://github.com/huskyhao/huawei-computing-practice.git
cd huawei-computing-practice
```

阅读相应项目 README 后运行其验证或复现脚本。鲲鹏项目的已保存数值结果可用普通电脑上的 Python 复核；重新执行硬件实验需要相应 AArch64 环境。昇腾项目重新推理需要匹配目标设备的 CANN，并在目标环境生成模型。

## 公开材料与原始记录

公开目录包含正文、配图、源码、复现步骤及脱敏后的数值结果。连接配置、凭证、个人目录、完整机器环境日志和板端模型二进制不作为本次新增公开材料上传；原始实验材料保留在本地及相应实验设备。各项目的公开版说明列出了具体范围。

其中异步 Stream 实验保留 19,200 条完成窗口记录和四个最小诊断对照的脱敏结果，性能数值与本地完整记录一致。

各实验的公开内容和迁移前的完整 Git 提交历史均集中保存在本仓库，按上述子目录访问与复现。

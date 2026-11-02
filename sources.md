# 官方资料与核查范围

核查日期：2026-11-02。文章中的性能、准确率、软件版本和设备告警来自本目录保存的真实实验结果；以下资料用于解释接口及工具行为。

- [scikit-learn：load_digits](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html)：8×8 手写数字、1797 条样本、64 维特征，像素值范围 0–16。
- [昇腾：Building a Model](https://www.hiascend.com/document/detail/en/canncommercial/850/appdevg/acldevg/aclcppdevg_000027.html)：ONNX 模型经 ATC 转换为 OM，ONNX 使用 `--framework=5`。该页面为较新版本文档；本文命令在实际安装的 CANN 8.0.0 上验证。
- [昇腾 CANN 8.0.0：get_run_mode](https://www.hiascend.com/doc_center/source/en/canncommercial/800/apiref/appdevgapi/aclpythondevg_01_0065.html)：`0` 表示 `ACL_DEVICE`，`1` 表示 `ACL_HOST`。
- [昇腾：AscendCL 同步 execute](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/910/API/ascendgraphapi/aclpythondevg_01_0145.html)：`acl.mdl.execute` 是等待执行完成的同步调用；本文接口亦通过实际运行验证。
- [昇腾：bytes_to_ptr / ptr_to_bytes](https://www.hiascend.com/document/detail/zh/Atlas200IDKA2DeveloperKit/23.0.RC2/Application%20Development%20Guide/aadgp/aclpythondevg_01_0052.html)：Python bytes 与指针互转，输入对象须维持有效生命周期。
- [昇腾：precision_mode](https://www.hiascend.com/document/detail/zh/canncommercial/80RC3/devaids/devtools/aoe/aoerc_16_0056.html)：说明 `allow_fp32_to_fp16` 下矩阵与矢量算子的精度策略。文章不将 FP32 输入输出等同于全程 FP32 计算。
- [昇腾：CANN 8.0.0.alpha001 安装指南](https://www.hiascend.com/doc_center/source/zh/CANNCommunityEdition/800alpha001/softwareinst/instg/CANN%208.0.0.alpha001%20%E8%BD%AF%E4%BB%B6%E5%AE%89%E8%A3%85%E6%8C%87%E5%8D%97%2001.pdf)：参考 NumPy 1.19.2–1.24、protobuf 3.20 等依赖要求。本实验最终组合以 requirements.txt 与实际成功执行为依据，不声称覆盖 CANN 全部版本。
- [PyPA virtualenv 安装说明](https://virtualenv.pypa.io/en/latest/how-to/install.html)：官方 zipapp 可在没有系统安装权限的环境中直接运行。

用户提供的鲲鹏博客列表链接通过网页工具访问失败，因此未引用其中未读取的博文，也未复制社区文章内容。

# 资料与证据来源

本次实测在 Orange Pi AIpro / Ascend310B1 / CANN 8.0.0 完成。模型与数据沿用同系列 ONNX→OM 实验，新增的独立变量是资源生命周期；计时、准确率、一致性和设备状态来自本次实际运行。

接口语义核查使用以下华为官方文档：

- [CANN 8.0.0：load_from_file](https://www.hiascend.com/doc_center/source/zh/canncommercial/800/apiref/appdevgapi/aclpythondevg_01_0139.html)：从 OM 文件加载模型、由系统管理运行内存及 Context 约束。
- [CANN 8.0.0：create_dataset](https://www.hiascend.com/doc_center/source/en/canncommercial/800/apiref/appdevgapi/aclpythondevg_01_0195.html)：Dataset 与描述地址、长度的 DataBuffer 的关系。
- [CANN 8.0.0：destroy_dataset](https://www.hiascend.com/doc_center/source/en/canncommercial/800/apiref/appdevgapi/aclpythondevg_01_0196.html)：描述对象的销毁与失效。
- [CANN 8.0.0：execute](https://www.hiascend.com/doc_center/source/zh/canncommercial/800/apiref/appdevgapi/aclpythondevg_01_0145.html)：同步执行、同一 Context 及共享模型调用的约束。
- [CANN 8.0.0：malloc](https://www.hiascend.com/doc_center/source/zh/canncommercial/800/apiref/appdevgapi/aclpythondevg_01_0110.html)：设备内存申请、释放及避免频繁申请释放的建议。

文档用于确认接口语义，不提供本次性能数据。没有硬件 trace，因此不把计时差异推断为某一种缓存、算子调度或分配器实现的根因。

训练、导出、虚拟环境准备与 ATC 辅助脚本沿用本合集已有数字分类实验；resource_lab.py 是本次新增的生命周期对照实现。

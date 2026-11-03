# 官方资料与证据范围

核查日期：2026-11-03。性能数值、输出一致性、`500002` 最小复现及设备状态来自本次 OrangePi 实机操作，不使用文档示例值作为实测数据。

- [CANN 8.0.RC2.alpha002：execute_async](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/80RC2alpha002/apiref/appdevgapi/aclpythondevg_01_0147.html)：异步返回与完成等待的区别，同一模型 ID 的多 Stream 并发限制，以及 Context 要求。
- [CANN：模型执行流程](https://www.hiascend.com/doc_center/source/zh/canncommercial/900/programug/acldevg/aclpythondevg_0032.html)：dataset/data buffer、输入输出内存、同步与异步模型执行流程。该页属于较新文档，本报告的实际命令与接口在板端 CANN 8.0.0 验证。
- [CANN 8.0.0.alpha002：AscendCL Python 应用开发指南](https://www.hiascend.com/doc_center/source/zh/CANNCommunityEdition/800alpha002/devguide/appdevg/aclpythondevg/CANN%E7%A4%BE%E5%8C%BA%E7%89%88%208.0.0.alpha002%20AscendCL%E5%BA%94%E7%94%A8%E8%BD%AF%E4%BB%B6%E5%BC%80%E5%8F%91%E6%8C%87%E5%8D%97%28Python%29%2001.pdf)：单线程多 Stream 示例使用不同模型 ID，执行后进行 Stream 同步。

“同一模型实例先同步后异步报 mix execute”是本次受控最小试验直接观察到的运行时行为，报告将范围限定为本机这套工具链和模型，不推断所有 CANN 版本均如此。

本次使用前一次实验的已验证 OM 和测试输入作为固定负载，未重新训练产生一份新准确率结果；新的实验变量是调用策略、等待频率和窗口大小。`models/` 和 `results/input-sha256.txt` 保存了本次副本与哈希。

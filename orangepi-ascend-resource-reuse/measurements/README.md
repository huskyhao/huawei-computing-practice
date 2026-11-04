# 可分享实测数据

formal/requests.csv 保留全部 24,000 条正式计时；每种策略 6,000 条，未过滤慢样本。startup/processes.csv 保存 12 个独立进程的计时。单位与统计口径见[博客](../blog.md)。

metadata.json 记录实际执行时通过的输出断言数量；完整逐样本输出和参考数组未在本快照公开。普通电脑复核验证统计与记录结构，不代替 NPU 推理。

summary.json 由 analyze_results.py 从 CSV 重算，environment.json 为机器日志的去身份摘要。原始 CSV 和 metadata 复制后逐字节校验，未改动数值。

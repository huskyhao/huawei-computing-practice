# 公开实验数值

- `formal.json`：32 个场景的设置、完成时间、吞吐与正确性统计，已去除进程内模型 ID。
- `formal_windows.csv`：19,200 个完成窗口的全部数值，每场景 600 个。
- `probe-summary.json`：四个最小对照的条件与返回码，不含 PID、完整日志或堆栈。
- `local-verification.json`：原始本地完整材料在发布前的核对记录。

平均值、中位数、P95、提交阶段与组末等待均可从 CSV 重算。各场景由 `boundary`、`window` 和 `policy` 标识；每条记录另含轮次、迭代编号以及三种时间，单位为微秒。

在本项目目录执行 `python scripts/verify_public_results.py` 可离线核对数值。

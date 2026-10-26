# 关键指标日志

用户最新要求优先：不需要 Ping/TCPing 整段原始输出，需要日志时间、实际命令、采集值、采集时间、上报时间、上报状态和上报值。

- [x] Metric 追加可选 command；复用实际采集命令构造函数，系统指标标明 psutil 接口。
- [x] Sender 在实际调用 send 前记录 sent_at，在返回响应后记录 acknowledged_at；not_sent 不虚构发送时间。
- [x] 可读日志每条指标集中显示上述关键字段；隐藏逐包输出与重复命令过程事件，保留真实错误。
- [x] JSON 审计保留结构化关键记录与堆栈，停止保存整段 stdout 和全量系统结构；命令结果仅保留退出码/耗时及短错误摘要。
- [x] 两位小数、整数精度、DEBUG 逐条确认、INFO 批量及旧接口兼容不变。
- [x] 回归、文档、审查；真实环境验证仍待现场执行。

验证记录：unittest 共 75 项，74 通过，1 项 Linux flock 跳过；compileall、git diff --check、两个离线包 verify 通过。增加采集失败命令上下文、实际发送时间、完整输出不入日志、长错误摘要截断测试。独立审查指出 stderr/未知 TCP 输出可能通过异常重入日志，已复现并修复。真实 Linux/Zabbix 新日志联调仍待现场执行。分支 codex/key-metric-logs，尚未提交推送。

# 审计去重

范围：只修改 audit.jsonl 的输出；agent.log、控制台、采集和发送行为保持原样。

方案：在审计 handler 过滤 metric_send 和 zabbix_response，保留完整
metric_delivery、metric_collected 及异常。JSON 省略与 event 相同的 message，
以及 metric_delivery 中为空字符串的 error。使用副本，不能修改共享 LogRecord。
相比改发送器，此方案不会影响普通日志或发送行为；保留采集记录可排查采集后未完成上报的情况。

1. 修改审计集成测试：四条指标事件输出两条审计，普通日志/控制台不变。
2. 添加格式测试：重复 message 和空 error 省略，非空错误、异常、空值及原记录保持。
3. 在 agent/logging_setup.py 实现仅供审计 handler 使用的 AuditFilter 和格式精简。
4. 更新 README 的审计事件说明；运行 python -m unittest discover -s tests -v 和 git diff --check。

检查重点：失败状态和异常不丢失；原始值及实际发送值保留；多个 handler 共享的记录不变。

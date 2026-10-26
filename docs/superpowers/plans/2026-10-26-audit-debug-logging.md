# 可配置详细审计日志

目标：YAML logging.level/console/retention_days 和 CLI --log-level；INFO 保持批量发送，DEBUG 记录原始采集输出、每条指标值及逐条服务端确认。

设计约束：Zabbix 只有批次汇总响应。DEBUG 模式逐条发送得到单指标响应，代价是更多请求；全部确认才标记 accepted，明确 failed 才标记 rejected，网络异常或不完整响应标记 unconfirmed，不能声称数据库持久化或告警处理完成。不自动重试。

- [x] 配置与 JSON Lines 日志格式测试：等级、控制台、保留、重复初始化、run_id/pid/thread/异常。
- [x] DEBUG 单指标发送与逐指标状态测试，INFO 批量兼容；每条记录含 host/key/value/clock、metric_id、服务端、响应计数。
- [x] 采集子进程原始 stdout/stderr、命令、退出码、超时与堆栈；系统/网卡原始值与 parsed metrics；记录发现判断和缓存更新。
- [x] 在入口绑定同一轮日志上下文，接入配置与 CLI；旧 INI 默认兼容。
- [x] 文档明确 DEBUG 请求开销、审计语义和日志保留；不是防篡改存证系统。全套测试和独立审查。

不新增第三方依赖；日志写入 log/agent.log 按天轮转。默认 INFO、console=true、retention_days=14。JSON 转义换行，原始输出完整保存且可机器解析。

验证：unittest 共 64 项，63 通过，1 项 Linux flock 跳过；Python compileall、git diff --check、两个离线包 verify、高级 YAML 与 CLI --log-level DEBUG 的配置检查均通过。端到端模拟测试确认 metric_collected 与 metric_delivery 具有相同 metric_id/run_id。独立审查指出按数量删除与按天保留冲突，已先复现再修复，只清理精确日期后缀且超期的日志，不清理手工备份。

实际 Linux/Zabbix 上报审计仍需现场验证。当前 codex/audit-debug-logging 分支尚未提交或推送；不引入新依赖，不改变 INFO 批量模式。

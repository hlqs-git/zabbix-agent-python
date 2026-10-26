# DEBUG 日志可读性优化

用户提供真实输出：终端逐条 JSON 冗长，同一指标多事件重复，线程原始输出和异常堆栈混杂。

目标：console/agent.log 为中文可读视图，每条 metric_delivery 合并值、发送值、结果、时间；audit.jsonl 保留所有原始结构化事件、响应和堆栈，run_id/metric_id 不变。保持 DEBUG 单条确认和 INFO 批量行为。

- [x] 增加可读视图与完整审计双输出、去重、失败状态、原始多行输出的测试。
- [x] 增加 ReadableFormatter 和仅作用于可读输出的过滤器；原始细节不删减，只从摘要移至 audit.jsonl。
- [x] metric_delivery 补充实际 wire_value，启动显示日志路径，摘要结构化；保留日志等级、控制台开关和两文件按天轮转。
- [x] 使用用户样本离线重放生成可读预览，核对 DNS 超时仍清楚显示；不向服务端发包。
- [x] 文档、全套测试、独立审查。旧 agent.log 不回写，audit.jsonl 为新的稳定机器格式入口。

验证记录：unittest 共 68 项，67 通过，1 项 Linux flock 跳过；compileall、git diff --check 和两个离线包完整性校验通过。用户样本离线重放：74 个事件投影为 32 个可读块，预览写入任务可视化目录，未将用户真实日志或地址写入仓库。独立审查无重要阻塞问题。真实 Linux 双日志安装运行待现场验证。当前 codex/readable-debug-logs 分支尚未提交推送。

用户追加要求：监控小数统一保留两位，完成后提交推送合并。已在发送边界新增 precision.metric_value，使用 Decimal(str(value)) 的 ROUND_HALF_UP，固定两位并归一化负零；整数和发现 JSON 不变。可读监控数值两位，审计 raw value 保留原始精度、wire_value 为实际发送字符串。新增失败基线后实现，完整测试 70 项，69 通过，1 项 Linux flock 跳过。合并范围包含已审查的可读日志双输出与本次精度处理。

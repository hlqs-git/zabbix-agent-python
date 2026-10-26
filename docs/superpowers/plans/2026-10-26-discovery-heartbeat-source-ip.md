# 发现心跳与 Ping 源地址

目标：发现列表首次/变化立即发送，未变化每小时发送一次；Ping 目标可选 source_ip，支持 namespace，保留现有 key 和 INI 兼容。

- [x] 增加发现状态回归测试：首次、未变化、3600 秒、变化、删除为空、重排、发送失败、损坏缓存、服务端/主机切换。
- [x] 在 discovery.py 增加独立持久化状态类，按 server/port/hostname/key 区分缓存；只在全部待发发现值确认成功后更新，原子写入，损坏时重新发现。
- [x] main 在现有进程锁内使用 log/discovery-state.json；检查配置不创建缓存；run_cycle 可注入缓存路径供测试与复用。
- [x] Target 增加末尾可选 source_ip；YAML 仅 Ping 接受 IPv4 源地址，检查清单展示；icmp 参数列表用 -I，不使用 shell。
- [x] 普通 Ping 及 Namespace Ping 测试配置、命令、调用传递及无字段兼容；同一目标多源需唯一 name。
- [x] 文档/高级示例、全套测试、独立审查。缓存 I/O 故障记录并下轮重试，不阻断其他指标采集。

默认每小时固定补发，不增加新用户必须填写的配置。比较的是发现集合（监控名称），不是波动指标或源 IP；同别名仅换探测地址不需要改变发现资源。列表排序规范化避免仅调整配置顺序就触发重发。服务端确认仅代表接收成功，不代表资源立即创建。

验证记录：unittest 共 53 项，52 通过，1 项 Linux flock 跳过。compileall、git diff --check、两个离线包完整性校验及高级 YAML 示例配置检查通过。独立审查无阻塞问题；另补异常缓存时间戳测试并修复负数/超大时间的恢复行为。真实 Linux 源 IP 绑定和 Zabbix 接收仍待现场联调。当前分支 codex/discovery-heartbeat-source-ip，尚未提交推送。

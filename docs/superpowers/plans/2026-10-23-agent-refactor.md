# Linux 监控采集程序重构实施计划

> 实施时使用 superpowers:executing-plans，按任务完成测试与验证。

**目标：** 保留 start.py、现有 INI 配置和已有 Zabbix key，解耦配置、采集、发现、调度和发送，修复已确认的数据与异常处理问题。

**架构：** 单次运行、cron 调度。采集器返回统一指标和错误，app 组织发现与采集，sender 批量发送；不引入常驻服务、数据库或插件框架。

**技术：** Python、标准库 unittest/concurrent.futures/subprocess/logging、psutil、py-zabbix。部署 Python 最低版本实施前根据现有依赖与类型语法确定并写入 README。

**设计依据：** 本次对话中已认可的渐进式重构方案。不得自行变更现有监控 key 或推送、合并代码。

## 全局约束

- 配置路径相对于项目文件，而非进程工作目录。
- 模块导入不得读取配置、创建日志文件或访问网络。
- 探测失败与采集执行异常必须区分；执行异常不伪造为目标丢包。
- 原有 Namespace、别名、功能开关和默认参数保留兼容处理。
- 运行锁面向 Linux；Windows 执行解析与模拟测试，不冒充 Linux 联调。
- 发现数据由完整配置生成，不能受目标在线状态影响。

## 文件职责

- agent/config.py：读取、规范化与校验配置。
- agent/models.py：目标、指标和采集结果数据结构。
- agent/collectors/system.py、network.py、icmp.py、tcp.py：采集与结果解析。
- agent/discovery.py：完整、去重的发现列表。
- agent/sender.py：Zabbix 转换、批量发送及结果检查。
- agent/runtime.py：有界线程池、Linux 进程锁。
- agent/logging_setup.py：显式初始化、日志轮转。
- agent/app.py：初始化与一轮任务编排。
- start.py：启动与退出码；core/main.py、package 下旧接口按需要保留薄兼容层。
- tests/：独立于真实网络与 Linux 命令的回归测试。

## Task 1：采集回归基线及正确性修复

- [ ] 在 tests/test_probes.py 编写失败测试：min/avg/max/mdev 分别为 1/2/3/4 时平均值为 2；0.5% 丢包不截断；全丢包为 100%；TCP 空输出和非法 JSON 返回采集错误。
- [ ] 运行 python -m unittest discover -s tests -v，确认新断言因原实现问题失败。
- [ ] 修复解析与异常分支，给命令添加 Python 层超时；保留现有函数接口至迁移完成。
- [ ] 验证缺少命令、超时、非正常退出、DNS 错误不会造成未捕获异常。

## Task 2：配置与结果结构

- [ ] 在 tests/test_config.py 验证当前 config.ini 的开关、别名及 Namespace 能正确解析，非法端口、空目标、重复 key 被拒绝。
- [ ] 新建 models.py，明确 Metric(host, key, value, timestamp) 及 CollectionResult(metrics, errors)；错误不得混入指标值。
- [ ] 新建 load_config(path)；将配置统一为系统开关、接口目标和探测目标集合，后续模块只消费规范化配置。
- [ ] 用 JSON 或 literal_eval 代替 eval；兼容 tcping_time，文档明确其单位为次数。
- [ ] 运行测试，确认导入配置模块没有文件写入或网络调用。

## Task 3：拆分采集与发现

- [ ] 在 tests/test_collectors.py 验证采集只返回结果、不发送网络请求；普通及 Namespace 目标保持旧 key。
- [ ] 将四类采集迁入 collectors，去除导入时日志初始化；调用参数由规范化目标传入。
- [ ] Namespace 网卡使用参数列表执行 ip -j -s link；解析 bytes 和状态，检查返回码并转为整数。
- [ ] 在 tests/test_discovery.py 验证多接口、多 ICMP/TCP 目标分别构成完整列表，离线目标保留，重复 key 拒绝。
- [ ] 实现 build_discovery(config)，每轮发送完整发现集合；DiscoveryHours 保留读取兼容并说明新行为。
- [ ] 运行全部测试。

## Task 4：发送、调度与日志

- [ ] 在 tests/test_sender.py 验证多指标一次调用、部分失败可识别、空集合不发送、网络异常保留失败状态。
- [ ] 实现 send_metrics(metrics)，复用 Sender，检查响应；重试必须有上限，记录可能重复发送的语义。
- [ ] 在 tests/test_runtime.py 验证并发上限、单任务异常隔离、任务结果汇总。
- [ ] 快速指标与耗时探测分批发送；每个结果使用实际采集时间，记录本轮成功失败数与耗时。
- [ ] 实现 Linux flock 进程锁，重复实例跳过且记录原因；锁文件不删除，避免 inode 竞争。
- [ ] 显式初始化轮转日志，避免重复 handler；日志路径可创建，保留期限有界。
- [ ] 接入 app.py、start.py 和旧入口兼容层；定义配置错误、采集或发送失败的非零退出码。

## Task 5：部署与验收

- [ ] 增加 requirements.txt；init.py 使用 sys.executable -m pip，安装失败返回非零状态。
- [ ] 更新 README：架构、配置兼容差异、依赖、权限、cron、超时、锁、日志与退出码。
- [ ] 执行 python -m unittest discover -s tests -v、python -m compileall agent core package start.py init.py、git diff --check。
- [ ] 单独检查敏感点：IPv6/含冒号目标明确支持或报错；Namespace 重名 key；无输出与未知 JSON 类型；发送部分失败；采集时接口消失。
- [ ] Linux 测试机验证真实 ICMP/TCP、Namespace、双实例锁和 cron；无环境时明确记录未验证，不声称联调通过。
- [ ] 核对 Zabbix 模板的浮点值类型、流量变化率、发现宏与资源丢失策略；模板未提供时列为上线前待验收项。
- [ ] 保留旧版本回退路径，先单台试运行，再推广。

## 进度

已在 codex/agent-refactor 分支完成本地重构，保留当前目录供用户直接审查；未创建额外 worktree，未提交或推送重构代码。

- 配置、模型、四类采集器、发现、批量发送、线程池、锁、日志及入口已实现，旧 package 采集接口保留为包装。
- 命令 python -m unittest discover -s tests -v：21 项测试，20 通过，1 项 Linux flock 专属测试在 Windows 跳过。
- 命令 python -m compileall -q agent core package start.py init.py：通过。
- 命令 python start.py --check-config：通过，1 个接口、4 个探测目标。
- 命令 git diff --check：通过，仅有本机 Git LF/CRLF 提示。
- 独立审查发现空发现集合不发送的问题，已先复现失败测试再修复；快速采集已合并为一批。
- 依赖安装尝试失败：files.pythonhosted.org 下载元数据超时。虚拟环境已创建，但真实依赖兼容性验证未完成。
- 测试使用系统临时目录时遭沙箱拒绝，授权后在沙箱外运行通过；不涉及真实网络探测。
- Linux 真实命令、Namespace、cron、Zabbix 接收及模板核对尚未完成，属于上线前验收项。
- Ruling：自动发送失败不重试，避免响应丢失时重复上报；目前无持久化补发。
- Ruling：每轮两类发现 key 均发送完整列表，包括空集合；关闭功能会进入服务端资源丢失策略，部署前需核对。
- Ruling：先发送快速采集批次，再运行并发送探测批次；有明确数据边界，系统指标不等待探测结束。

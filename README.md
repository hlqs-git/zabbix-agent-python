# Python Linux Zabbix 采集器

采集 Linux 系统负载、内存、根分区使用率、网卡累计字节计数、ICMP 和 TCP 可达性，支持 Linux network namespace，通过 Zabbix Sender 协议上报。

## 安装和运行

运行环境：Linux、Python 3.8 及以上。Python 3.13 等较新版本建议使用有对应 wheel 的新版 psutil，不使用仓库内旧 psutil 源码包。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# 或使用当前解释器安装：python3 init.py

# TCP 探测沿用原 tcping 二进制；需确认其架构和操作系统兼容
chmod +x package/download/tcping
ln -s /absolute/path/zabbix-agent-python/package/download/tcping /usr/local/sbin/tcping

.venv/bin/python start.py --check-config
.venv/bin/python start.py
.venv/bin/python start.py --config /absolute/path/custom.ini
```

修改 `conf/config.ini` 中的 Server、ServerPort、Hostname 和采集目标。Hostname 必须对应 Zabbix 主机的技术名称。启动路径不依赖当前工作目录，无需创建系统 python 软链接。

依赖系统命令 `ping`（iputils）、`ip`（iproute2）和启用 TCP 时的 tcping。Namespace 使用 `ip -j -s link`，要求 iproute2 支持 JSON 输出。执行 Namespace 命令通常需要 root 或对应权限；普通 ping 权限取决于发行版配置。运行用户需能写入项目的 log 目录。

cron 示例：

```cron
* * * * * /absolute/path/zabbix-agent-python/.venv/bin/python /absolute/path/zabbix-agent-python/start.py
```

程序每次执行一轮后退出。Linux 文件锁防止同一项目目录的任务重叠，旧任务未结束时新实例跳过；不要删除运行中的 `log/agent.lock`。探测次数、超时和目标数量应与 cron 周期匹配，线程池排队也会增加整轮耗时。默认 ICMP 为 50 秒，TCP 为 50 次；TCP 最坏耗时可能超过一分钟，锁会避免重叠但可能跳过下轮。

## 结构

- `agent/app.py`：初始化和一轮任务编排。
- `agent/config.py`、`models.py`：配置校验及规范化数据结构。
- `agent/collectors/`：系统、网卡、ICMP、TCP 采集，不发送数据。
- `agent/discovery.py`：由完整配置生成自动发现列表。
- `agent/sender.py`：批量上报、响应检查及失败结果。
- `agent/runtime.py`、`logging_setup.py`：线程池、进程锁及日志轮转。
- `start.py`、`core/main.py`：保留启动入口。
- `package/*.py`：旧采集与单指标发送接口的兼容包装；core/main.py 原内部辅助函数不再作为接口提供。

## 配置兼容和行为变化

已有 INI 功能开关、网卡别名、Namespace 及监控 key 保留。新增可选配置：

```ini
[runtime]
workers = 16
send_timeout = 5
```

`workers` 为最大并发任务数，`send_timeout` 为每次发送的 socket 超时秒数。`[ping]` 可设置 `tcping_count` 和 `tcping_timeout`（秒）；未设置 count 时继续读取旧 `tcping_time`，该旧字段实际代表次数。

- 自动发现每轮发送同类目标的完整列表，不再按单个目标发送；旧 `DiscoveryHours` 不再控制执行时间。
- 同一类监控名称必须唯一，跨 Namespace 重名必须配置不同别名。旧 ns_ping_address 不能表达别名，因此重名需要调整目标配置；本次未新增 Namespace ping 别名语法。
- 空目标、错误端口、重复 key、危险 key 字符在启动时拒绝；当前目标语法和 TCP 探测仅支持 IPv4/域名，不支持 IPv6。
- Ping 平均时延修正为 avg，小数丢包率保留；100% 丢包时延为 0，需结合丢包率判断。
- 命令不存在、超时、输出错误记为采集失败，不伪造 100% 丢包，也不发送该目标的错误数值。
- 自动发现、快速采集和探测结果分批上报；发现发送完成不保证服务端已即时创建监控项，首次运行可能部分失败，需检查后续周期。
- 网络异常或部分拒收记录失败，不自动重发，避免响应丢失时重复写入。当前不提供持久化补发。
- 日志为 `log/agent.log`，按天轮转，保留 14 份历史文件。退出码：0 成功或重叠跳过，1 采集/发送/运行失败，2 配置错误或不支持的运行平台。

## 测试与上线检查

```bash
python -m unittest discover -s tests -v
python -m compileall agent core package start.py init.py
python start.py --check-config
```

单元测试模拟命令、设备和发送边界，不向真实 Zabbix 发包。Windows 可执行配置校验与单元测试，实际采集限定 Linux。

上线前用一台 Linux 设备验证真实 ICMP/TCP、Namespace、cron、双实例锁和 Zabbix 接收。核对原模板 `Template_sysload_Python_Nodata v1` 或 `Template_sysload_Python v1`：丢包率及延迟需为浮点监控项；流量上报累计字节数，应在服务端配置变化率和需要的单位转换；检查发现宏、资源丢失策略和 nodata 告警。模板未包含在本仓库。

重构前版本标签：`pre-refactor-2026-10-23`，对应提交 `1a4b972`（version 1.09）。需要回退时先保存当前改动，再从此标签建立恢复分支。

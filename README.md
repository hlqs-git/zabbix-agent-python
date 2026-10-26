# Python Linux Zabbix 采集器

采集 Linux 系统负载、内存、根分区使用率、网卡累计字节计数、ICMP 和 TCP 可达性，支持 Linux network namespace，通过 Zabbix Sender 协议上报。

## 安装和运行

统一离线安装入口：`bash install.sh`。计划覆盖 Ubuntu 24.04 amd64 和 CentOS Linux 8.5 x86_64，系统包和 Python wheels 随项目放在 `offline/<平台>/` 内。

**当前完整系统包尚未构建和断网验收，暂不能把此分支作为开箱即用的离线安装包交付。** 两平台的 Python wheels 已内置；完整构建和交付状态见 [offline/README.md](offline/README.md)。最终用户只需整个项目，不需要自己再下载包；维护者需要先在联网 Docker 主机完成一次构建。

```bash
# 维护者：在联网 Docker 主机准备项目内完整依赖并执行断网验收
bash scripts/build-offline.sh ubuntu-24.04-amd64
bash scripts/build-offline.sh centos-8.5-x86_64

# 最终用户：拿到完整项目后，在对应离线 Linux 主机执行
bash install.sh
```

脚本不覆盖配置、不添加 cron、不启动采集。`python3 init.py` 现为统一安装器的兼容入口。下面的手工方式仍可用于联网部署和排查。

运行环境：Linux、Python 3.8 及以上。Python 3.13 等较新版本建议使用有对应 wheel 的新版 psutil，不使用仓库内旧 psutil 源码包。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# TCP 探测沿用原 tcping 二进制；需确认其架构和操作系统兼容
chmod +x package/download/tcping
ln -s /absolute/path/zabbix-agent-python/package/download/tcping /usr/local/sbin/tcping

.venv/bin/python start.py --check-config
.venv/bin/python start.py
.venv/bin/python start.py --config /absolute/path/custom.yaml
```

Ubuntu 24.04 手工安装前先执行 `apt-get update && apt-get install -y python3-venv iputils-ping iproute2`。若此前创建 `.venv` 失败，安装 venv 系统包后重新执行 `python3 -m venv .venv`，再安装 requirements；系统包安装不会自动修复已有的半成品虚拟环境。

首次使用修改 `conf/config.yaml`：填写 `zabbix.server` 和 `zabbix.hostname`，再修改需要监控的网卡、Ping、TCP 目标；不需要的项目直接删除。hostname 必须对应 Zabbix 主机的技术名称。默认文件中的地址和接口仅为示例，请按实际环境修改。启动路径不依赖当前工作目录，无需创建系统 python 软链接。

先执行 `--check-config` 核对连接信息、监控目标、别名和探测参数，再运行采集。配置检查不会连接 Zabbix 或执行探测；检查通过不代表接口存在、目标可达或服务端接收成功。YAML 缩进使用空格，不使用 Tab。

依赖系统命令 `ping`（iputils）、`ip`（iproute2）和启用 TCP 时的 tcping。Namespace 使用 `ip -j -s link`，要求 iproute2 支持 JSON 输出。执行 Namespace 命令通常需要 root 或对应权限；普通 ping 权限取决于发行版配置。运行用户需能写入项目的 log 目录。

cron 示例：

```cron
* * * * * /absolute/path/zabbix-agent-python/.venv/bin/python /absolute/path/zabbix-agent-python/start.py
```

程序每次执行一轮后退出。Linux 文件锁防止同一项目目录的任务重叠，旧任务未结束时新实例跳过；不要删除运行中的 `log/agent.lock`。探测次数、超时和目标数量应与 cron 周期匹配，线程池排队也会增加整轮耗时。YAML 默认 ICMP 为 50 秒，TCP 为 10 次；旧 INI 默认 TCP 仍为 50 次。整轮超过执行周期时会跳过下轮。

## 结构

- `agent/app.py`：初始化和一轮任务编排。
- `agent/config.py`、`models.py`：配置校验及规范化数据结构。
- `agent/collectors/`：系统、网卡、ICMP、TCP 采集，不发送数据。
- `agent/discovery.py`：由完整配置生成自动发现列表。
- `agent/sender.py`：批量上报、响应检查及失败结果。
- `agent/runtime.py`、`logging_setup.py`：线程池、进程锁及日志轮转。
- `start.py`、`core/main.py`：保留启动入口。
- `package/*.py`：旧采集与单指标发送接口的兼容包装；core/main.py 原内部辅助函数不再作为接口提供。

## 配置方法

`conf/config.yaml` 只放常用配置，`conf/config.example.yaml` 展示高级字段；后者不会自动加载。每个目标一条记录，写了就监控，删除该项或填写 `[]` 就不监控，不需要单独设置开关。`system: true` 开启系统指标，false 或省略表示关闭。

```yaml
zabbix:
  server: zabbix.example.com
  hostname: linux-01

system: true
interfaces:
  - device: eth0
ping:
  - address: 1.1.1.1
tcp:
  - address: example.com
    port: 443
```

可选参数：

| 位置 | 字段 | 默认值或含义 |
|---|---|---|
| zabbix | port | 10051 |
| zabbix | send_timeout_seconds | 5 秒，每次发送的 socket 超时 |
| runtime | max_workers | 16，最大并发任务数 |
| 任意目标 | name | 可选监控别名；省略时使用 device 或 address |
| 任意目标 | namespace | 可选 Linux network namespace；省略时为普通目标 |
| ping 目标 | duration_seconds | 50 秒，每轮探测持续时间 |
| tcp 目标 | count | 10 次，每轮探测次数 |
| tcp 目标 | connect_timeout_seconds | 1 秒，单次连接超时 |

TCP 最终监控名称由 `name`（或 address）加 `:port` 生成，例如 `web:443`，不要在 name 中重复填写端口。网卡名称在全部网卡目标中唯一，Ping/TCP 最终名称在全部探测目标中唯一；不同 Namespace 重名时填写不同 name。拼错字段、重复字段、错误类型或缺失端口会直接报告字段位置。

## 旧版 INI 迁移

仍支持 `--config /path/config.ini`，会显示迁移提示。旧格式示例保存在 `conf/config.legacy.example.ini`。未指定路径时，只加载 conf 目录下唯一存在的 `config.yaml`、`config.yml` 或 `config.ini`；若多个文件并存，必须通过 `--config` 指定，避免升级后静默切换目标。

将旧的 `if_nic` 转为 interfaces 的 device，别名转为 name；ping_address 转为 ping 的 address；TCP 地址拆成 address 和 port。迁移时 name 沿用旧别名，未使用别名则省略，保持服务端 key 一致。旧 tcping_time 是次数，新版使用 count；需要保持原采样量时显式填写 `count: 50`。仅复制旧配置中已启用的目标，旧已关闭段落中的示例不要迁入。

INI 仍支持原运行参数：

```ini
[runtime]
workers = 16
send_timeout = 5
```

`workers` 为最大并发任务数，`send_timeout` 为每次发送的 socket 超时秒数。`[ping]` 可设置 `tcping_count` 和 `tcping_timeout`（秒）；未设置 count 时继续读取旧 `tcping_time`，该旧字段实际代表次数。

- 自动发现每轮发送同类目标的完整列表，不再按单个目标发送；旧 `DiscoveryHours` 不再控制执行时间。
- YAML 的 Ping/TCP 均支持 namespace 和 name；旧 INI 的 Namespace Ping 别名语法未扩展。
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

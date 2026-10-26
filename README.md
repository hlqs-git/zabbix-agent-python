# Python Linux Zabbix 采集器

采集 Linux 系统负载、内存、根分区使用率、网卡累计字节计数、ICMP 和 TCP 可达性，支持 Linux network namespace，通过 Zabbix Sender 协议上报。

## 安装和运行

采用轻量离线安装：项目只携带 Python wheels、pip 引导包和一份 tcping，不包含系统 deb/rpm。目标主机需要先具备系统 Python、venv、ping 和 ip。基础工具齐备后，安装应用依赖的整个过程不访问互联网。

### 1. 管理员准备基础环境（仅一次）

Ubuntu 24.04 amd64：

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv iputils-ping iproute2 ca-certificates
```

CentOS Linux 8.5 x86_64：

```bash
sudo dnf install -y python39 python39-pip iputils iproute ca-certificates
```

CentOS 需要可用的归档源或内网软件源，安装脚本不自动修改软件源。必须使用 Python 3.9，系统自带的 3.6 不适用此离线包。完全隔离的主机需由管理员预装这些基础工具；项目不负责离线安装操作系统组件。

### 2. 安装项目并核对配置

```bash
bash install.sh
# 修改配置后再检查、启动
.venv/bin/python start.py --check-config
.venv/bin/python start.py
# 或选择其他配置
.venv/bin/python start.py --config /absolute/path/custom.yaml
```

无需 root 即可安装项目（项目目录需要可写）。安装器检查基础工具和离线包完整性，然后创建或修复 `.venv`，仅从本地 wheels 安装 Python 库，把内置 tcping 复制到 `.venv/bin/tcping`。不覆盖配置、不写系统目录、不添加 cron、不启动采集。`python3 init.py` 保留为兼容入口。

如果缺少基础工具，脚本会列出缺失项及相应安装命令；如果 `.venv` 使用了其他 Python 版本，会要求先备份并移出旧环境。无需给系统 python 创建软链接，也无需给 tcping 创建系统软链接。

项目已内置两个平台的 Python 离线库和校验清单，总共约 15 MB（含一份 tcping，不计 Git 历史和运行时 .venv）。详细包结构、维护者准备方式和可选断网验收见 [offline/README.md](offline/README.md)。尚未在真实 Linux/Docker 环境完成新版安装验收，本地测试不替代实际安装验证。

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
| ping 目标 | source_ip | 可选源 IPv4 地址；省略时由系统路由选择 |
| tcp 目标 | count | 10 次，每轮探测次数 |
| tcp 目标 | connect_timeout_seconds | 1 秒，单次连接超时 |

TCP 最终监控名称由 `name`（或 address）加 `:port` 生成，例如 `web:443`，不要在 name 中重复填写端口。网卡名称在全部网卡目标中唯一，Ping/TCP 最终名称在全部探测目标中唯一；不同 Namespace 重名时填写不同 name。拼错字段、重复字段、错误类型或缺失端口会直接报告字段位置。

丢包率、时延、CPU、内存/磁盘百分比、系统负载等浮点指标，上报时四舍五入并固定保留两位小数，例如 45.668→45.67、5.6→5.60；整数状态和累计字节计数不转换为浮点，不丢失精度。可读日志同样显示两位小数；audit.jsonl 的 value 仍保留原始精度，wire_value 记录实际发送的两位小数字符串。

指定 Ping 源 IP 的示例：

```yaml
ping:
  - address: 1.1.1.1
    name: dns_via_wan
    source_ip: 192.0.2.10
```

`source_ip` 只接受 IPv4 地址，不接受接口名；示例地址需替换成实际配置在本机接口上的地址。与 namespace 同时使用时，该地址必须在对应 Namespace 中存在。未填写时保持原来的路由选择行为。对同一目标使用多个源 IP 时，每条配置必须使用不同 name，以区分服务端监控项。TCP 暂不支持 source_ip。

## 自动发现发送策略

首次运行发送网卡与探测目标的完整发现列表；发现集合变化后，在下一次程序运行时立即发送变化的规则；集合不变时每 3600 秒补发一次。规则中最后一个目标删除后仍发送空列表。仅调整配置顺序、修改不影响监控名称的源 IP 或采样参数，不触发资源发现。普通 CPU、流量、丢包率等指标仍每轮采集和上报。

确认接收成功后，发现状态才原子保存到 `log/discovery-state.json`，按 Server、端口、Hostname 和发现 key 分别记录。批次失败或部分失败不更新状态，下轮重试。缓存丢失、损坏或系统时钟回退时重新发送完整发现；缓存写入失败不会中断其他指标上报。默认命令入口在原进程锁内操作状态，无需新增配置字段。删除该缓存文件可使下一轮重新发现。

服务端接收发现数据不保证监控项即时创建，首次运行可能仍有个别指标被拒绝；后续周期再观察。若修改服务端监控项原型而客户端目标未变，最长需等待下一次每小时补发。

## 日志与详细审计

默认 INFO。终端和 `log/agent.log` 输出中文关键指标日志，`log/audit.jsonl` 保存结构化审计事件；两份文件均按天轮转，启动和轮转时清理超过保留天数的历史文件。等级作用于两份日志，逐指标信息需使用 DEBUG。可选配置：

```yaml
logging:
  level: DEBUG
  console: true
  retention_days: 14
```

支持 DEBUG、INFO、WARNING、ERROR、CRITICAL（大小写不敏感）。旧 INI 可添加同名 `[logging]` 段。临时排障无需修改配置：

```bash
.venv/bin/python start.py --log-level DEBUG
```

命令行等级优先于配置；`--check-config --log-level DEBUG` 仅检查，不创建日志、不发送数据。

每条指标只占一行，以 `|` 分隔日志时间、key、采集值、执行命令、采集时间、上报时间、上报值和状态，可直接 grep 过滤。错误中的换行、回车及 Unicode 换行符会转义，不产生额外日志行。上报时间是在调用发送器前记录的实际时间，不使用日志时间代替。系统/普通网卡使用 psutil，没有 Shell 命令，因此记录实际采集 API；Namespace 和源 IP 均包含在对应探测命令中。不再展开 Ping/TCPing 逐包输出、整段统计或全量系统结构。

```text
2026-10-26 13:57:59.391+08:00 [DEBUG] [上报成功] ping_get[dns,delay] | 采集值=45.67 | 上报值=45.67 | 执行命令=ping -w 50 -i 0.25 -q 1.1.1.1 | 采集时间=2026-10-26 13:57:59+0800 | 上报时间=2026-10-26 13:57:59.370+08:00 | 主机=linux-01 | 耗时=20.973ms
```

例如 `grep -F 'ping_get[dns,delay]' log/agent.log` 会保留该指标的完整关键字段。单行规则对更新后写入的日志生效，旧多行日志不会自动重写。

`audit.jsonl` 采用每行一条 JSON，包含带时区的时间、level、run_id、pid、thread、事件名及 fields。每轮共享 run_id，每条指标通过 metric_id 关联采集、发送和结果；clock 为采集时间，sent_at 为开始上报时间，acknowledged_at 为响应返回时间（均为 Unix 秒）。value 保留解析后原始数值，wire_value 是实际发送值。命令结果只记录命令、退出码、耗时和最多 512 字符的错误摘要，不再记录完整 stdout/stderr；异常堆栈仍可用于定位失败。旧日志不自动回写清理。

DEBUG 审计文件包含：

- `collector_start`：目标、别名、Namespace、源 IP 与探测参数。
- `command_start` / `command_result` / `command_error`：实际参数列表、退出码、耗时和短错误摘要；不含整段原始输出。
- `metric_collected`：每条指标的 host、key、采集命令/API、采集值 value、clock、metric_id。
- `metric_send`：实际发送值 wire_value，以及目标 Server 和端口。
- `zabbix_response` / `metric_delivery`：服务端响应、结果计数、耗时、sent_at/acknowledged_at 和逐指标确认状态；没有实际发送时 sent_at 为空。
- `discovery_decision` / `discovery_cache_saved`：首次/变化/心跳/跳过的判断和缓存更新。

| metric_delivery.status | 含义 |
|---|---|
| accepted | 收到有效响应，服务端确认处理成功 |
| rejected | 收到有效响应，服务端明确报告该指标失败 |
| unconfirmed | 已调用发送，但连接异常、响应丢失或不完整，无法确认是否接收；不自动重发 |
| not_sent | 在构建数据或初始化发送器阶段失败，尚未调用发送 |

Zabbix 批量响应只有汇总计数，无法定位部分失败中的具体指标。因此 **DEBUG 会逐条发送** 来取得单指标响应，增加连接数量、执行时间和日志量；INFO 等其他等级维持批量发送，记录执行摘要与错误。正常采集仍使用并发，逐指标发送发生在结果汇总阶段。

这份日志可核对“采集了什么、发送了什么、服务端是否确认”，accepted 不代表已经核验服务端数据库持久化或触发器执行；本地轮转文件也不是防篡改存证。需要长期保留审计记录时，应在清理前归档文件。配置解析失败或日志目录本身无法初始化时，错误只输出终端。

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

- 自动发现采用变化立即发送、未变化每小时补发；每次发送完整集合。旧 `DiscoveryHours` 不再控制执行时间。
- YAML 的 Ping/TCP 均支持 namespace 和 name；旧 INI 的 Namespace Ping 别名语法未扩展。
- 空目标、错误端口、重复 key、危险 key 字符在启动时拒绝；当前目标语法和 TCP 探测仅支持 IPv4/域名，不支持 IPv6。
- Ping 平均时延修正为 avg，小数丢包率保留；100% 丢包时延为 0，需结合丢包率判断。
- 命令不存在、超时、输出错误记为采集失败，不伪造 100% 丢包，也不发送该目标的错误数值。
- 自动发现、快速采集和探测结果分批上报；发现发送完成不保证服务端已即时创建监控项，首次运行可能部分失败，需检查后续周期。
- 网络异常或部分拒收记录失败，不自动重发，避免响应丢失时重复写入。当前不提供持久化补发。
- 可读日志为 `log/agent.log`，完整审计为 `log/audit.jsonl`，等级、控制台输出与历史保留天数可配置。退出码：0 成功或重叠跳过，1 采集/发送/运行失败，2 配置错误或不支持的运行平台。

## 测试与上线检查

```bash
python -m unittest discover -s tests -v
python -m compileall agent core package start.py init.py
python start.py --check-config
```

单元测试模拟命令、设备和发送边界，不向真实 Zabbix 发包。Windows 可执行配置校验与单元测试，实际采集限定 Linux。

上线前用一台 Linux 设备验证真实 ICMP/TCP、Namespace、cron、双实例锁和 Zabbix 接收。核对原模板 `Template_sysload_Python_Nodata v1` 或 `Template_sysload_Python v1`：丢包率及延迟需为浮点监控项；流量上报累计字节数，应在服务端配置变化率和需要的单位转换；检查发现宏、资源丢失策略和 nodata 告警。模板未包含在本仓库。

重构前版本标签：`pre-refactor-2026-10-23`，对应提交 `1a4b972`（version 1.09）。需要回退时先保存当前改动，再从此标签建立恢复分支。

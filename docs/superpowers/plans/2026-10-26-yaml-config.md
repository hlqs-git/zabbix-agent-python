# YAML 配置优化实施记录

目标：新用户只需填写 Zabbix 连接信息和目标列表。保留 INI 加载兼容，采集与上报接口不变。

设计：使用 PyYAML 安全加载器；写了就采集，删除或 [] 表示不采集，system 缺省为 false。常用默认值：端口 10051、并发 16、发送超时 5 秒、Ping 50 秒、TCP 10 次及单次超时 1 秒。每个目标可按需设置 name、namespace 和带单位的探测参数。

- [x] 先添加测试，验证旧实现无法加载 YAML、无字段级错误及无检查清单。
- [x] 新增严格 YAML 解析，拒绝重复字段、未知字段、错误类型、非法数值及重复监控名称。
- [x] 新增 config.yaml 最简配置和 config.example.yaml 高级示例；旧样例改名 config.legacy.example.ini。
- [x] 默认只自动加载唯一存在的 config.yaml/config.yml/config.ini；并存时要求 --config，防止隐式切换目标。
- [x] --check-config 展示连接信息、目标、别名、Namespace 和采样参数，不连接设备或服务端。
- [x] 旧 INI 显示迁移提示；等价迁移配置测试比较完整规范化结果，确保 key 与参数不变。
- [x] 项目虚拟环境安装 PyYAML 6.0.3，新增 requirements 约束 >=6.0.1,<7。
- [ ] Linux 与 Zabbix 真实联调仍待部署环境验证。

说明：只在 codex/yaml-config 分支修改，不自动提交、推送或合并。系统临时目录测试需在本机沙箱外授权执行。

验证：.venv/Scripts/python -m unittest discover -s tests -v 共 30 项，29 通过，1 项 Linux flock 测试在 Windows 跳过。默认 YAML、高级 YAML 和旧 INI 的 --check-config 均通过；compileall 和 git diff --check 通过。仅安装 PyYAML，不执行真实设备探测或 Zabbix 上报。

# 轻量离线安装调整

按用户最新要求：不分发系统 deb/rpm，文档列出 Python/venv/ping/ip 等前置依赖；只内置 Python wheels、pip 和一份共享 tcping。

- [x] 修改 bundle schema，校验 Python 依赖与共享 tcping，拒绝混入系统包；无需 cmp、VALIDATED。
- [x] 安装器只检查系统前置条件，创建/修复 venv、本地安装 Python 库、把 tcping 复制到项目 venv；不调用 apt/dnf、不写系统目录、不要求 root。
- [x] 采集器使用项目内安装的 tcping，保留旧系统路径回退。
- [x] 维护者准备工具直接下载指定 Linux wheels 并生成清单，不再依赖 Docker 构建系统包；可选 Docker 只验证预装基础环境后的断网应用安装。
- [x] 生成两个完整轻量离线目录，更新文档、大小与迁移说明；旧系统包由用户移出项目，不能静默删除。
- [x] 回归测试、脚本语法、校验和、配置检查；真实 Linux 断网安装未执行时明确记录。

本地验证：unittest 40 项，39 通过，1 项 Linux flock 跳过。六个 Bash 脚本通过 bash -n，compileall、git diff --check 及两个实际轻量目录的 verify 均通过。依赖文件约 15.4 MB（offline 及共享 tcping）；不含 Git 历史、旧系统包和安装后的 .venv。

独立审查发现自定义 bundle 路径可能校验另一份 tcping，已先写失败测试再修复：安装器显式传入当前项目实际复制的二进制路径。升级 wheels 的文档说明需先移出旧 wheel，避免新旧版本混用。新版完整安装与可选 Docker 断网验收尚未在真实 Linux 上执行，不能将本地逻辑测试表述为部署验证。

当前分支 codex/lightweight-offline，尚未提交、推送或合并。

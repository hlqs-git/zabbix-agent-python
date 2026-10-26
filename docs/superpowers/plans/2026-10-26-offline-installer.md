# 统一离线安装计划

目标：项目目录内携带目标平台依赖，最终用户只运行 bash install.sh。在线准备是维护者流程，离线部署不访问网络。

平台：Ubuntu 24.04 amd64（Python 3.12）、CentOS Linux 8.5 x86_64（Python 3.9）。CentOS Stream 不混用。CentOS Linux 使用 vault 归档，仅在构建容器配置归档源，不修改用户主机仓库。

- [x] 实现平台识别、清单生成和校验测试：平台不符、缺包、篡改必须在系统变更前失败。
- [x] 实现 install.sh，校验完整包后通过本地 apt/dnf 安装，创建/修复 venv，从本地 wheels 安装并检查配置。
- [x] 实现维护者构建脚本：干净目标容器下载系统依赖闭包、全部 Python wheels、pip 引导包与 tcping，生成清单和 SHA256。
- [x] 提供两个目标平台的 Python 离线包，禁止源码包和下载时使用宿主机 Windows wheels。
- [ ] 完整系统包和依赖在容器内断网安装验收后才能标记为可交付，未生成完毕不生成 ready 清单。
- [x] 更新 README、系统 venv 前置说明、旧 init.py 转发与部署命令。

约束：保留配置、不创建 cron、不启动采集、不覆盖不同的现有 tcping；无需在目标主机 Docker。系统包不能用 --nodeps 绕过依赖。构建目录在 offline 内，完整包作为普通文件随项目携带，不使用 Git LFS 指针替代。

环境限制：当前 Windows 无可用 Docker/WSL，不能声称已完成两平台的系统包准备和断网验证。实现与 Python 包准备可本地进行，剩余 Linux 构建状态需明确记录。

本地验证：完整 unittest 34 项，33 通过，1 项 Linux flock 跳过；四个 Bash 文件通过 bash -n，Python compileall、git diff --check 通过。独立审查指出完整预检应在包管理器前，已拆出无 Python 依赖的 check-bundle.sh，采用 bundle.meta 和 SHA256SUMS 为权威清单；测试验证合法包通过、格式不支持即使校验和正确也被拒绝。修复 Windows 写入清单的换行兼容问题。

用户已确认有可用联网 Linux 构建环境；等待 SSH 地址/用户/端口、现有密钥方式和 Docker 状态。后续需同步当前未提交工作、分别执行两平台构建和断网验证，再取回完整 deb/rpm payload。当前仅有 Python wheels，未产生 VALIDATED，不得标记离线交付完成。

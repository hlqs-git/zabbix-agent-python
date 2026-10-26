# 轻量离线依赖

目标：Ubuntu 24.04 amd64 / Python 3.12、CentOS Linux 8.5 x86_64 / Python 3.9。只携带应用依赖，不包含操作系统组件。

## 随项目提供

- `ubuntu-24.04-amd64/wheels`：Python 3.12 的 Linux wheels。
- `centos-8.5-x86_64/wheels`：Python 3.9 的 Linux wheels。
- 每个平台的 `requirements.lock`、`manifest.json`、`SHA256SUMS`、`bundle.meta`。
- `package/download/tcping`：两个平台共享一份二进制，校验值记录在每份 manifest 中。

包含 pip 25.1.1、psutil 5.9.8、py-zabbix 1.1.7、PyYAML 6.0.2；上述版本不需要其他 Python 运行依赖。新增依赖时准备工具会一并下载其间接依赖。SHA256 用来检查文件损坏，不代替来源认证。

## 基础环境

Ubuntu 由管理员预装 `python3.12 python3.12-venv iputils-ping iproute2 ca-certificates`；CentOS 预装 `python39 python39-pip iputils iproute ca-certificates`。CentOS 自带 Python 3.6 不用于本项目。项目不会安装系统包或改软件源。

目标主机执行 `bash install.sh` 即可安装项目依赖；不需要 Docker，不需要 cmp，不要求全局安装 pip，不向 `/usr/local/sbin` 写入文件。配置、cron 和采集启动由用户自己管理。

## 维护者准备离线库

升级依赖版本前，先将对应平台原来的 wheels 目录备份并移出项目，再准备新版本，避免同一库的新旧 wheel 混用。准备工具遇到重复发行版会拒绝生成交付清单，不会自动删除已有包。

提供的 wheels 已在项目中，无需用户再构建或下载。维护者升级库时可在有 pip 的联网机器执行（支持 Windows/Linux，始终下载目标 Linux 架构的 wheel）：

```bash
python3 scripts/prepare-wheels.py ubuntu-24.04-amd64
python3 scripts/prepare-wheels.py centos-8.5-x86_64
```

已有完整 wheel 文件时，不联网重新生成清单：

```bash
python3 scripts/prepare-wheels.py ubuntu-24.04-amd64 --seal-only
python3 scripts/prepare-wheels.py centos-8.5-x86_64 --seal-only
```

`bash scripts/build-offline.sh <平台>` 是上述准备命令的兼容包装，不再启动 Docker、不再下载系统包。生成清单会使旧 VALIDATED 验收记录失效，安装器不以该标记作为门槛。

可选真实断网验收（仅维护者，需要联网 Docker）：

```bash
bash scripts/validate-offline.sh ubuntu-24.04-amd64
bash scripts/validate-offline.sh centos-8.5-x86_64
```

验证脚本先在测试镜像中联网安装文档规定的基础环境，然后断网测试应用首次安装、重复安装和测试集。系统包只进入 Docker 测试镜像，不写入项目目录。通过后生成可选 VALIDATED 记录。

## 从旧版全量包迁移

旧构建生成的 `debs/`、`rpms/` 和平台目录中的 `bin/` 不再需要，应先移出项目目录；不要带入新版轻量包。原 `package/download/tcping` 保留。

已经在构建主机产生旧版未跟踪清单的，应先把旧平台输出目录备份到项目外，避免 git pull 时未跟踪文件与新版清单冲突。也可以另建目录克隆新版，迁移自己的 conf 配置；旧包留在原目录直到确认不再使用。

当前 schema 为 2，旧 schema 1 的系统全量包不被新版安装器接受。原来的基础环境无需卸载；重新执行新版安装器会复用已安装的 Python、ping 和 ip。

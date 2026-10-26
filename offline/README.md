# 项目内置离线依赖

目标：ubuntu-24.04-amd64（Python 3.12）、centos-8.5-x86_64（Python 3.9）。CentOS 指 CentOS Linux 8.5.2111，不包含 Stream、Rocky 或 AlmaLinux。

**当前状态：尚未生成并验收完整系统离线包。没有 VALIDATED 的目录不能作为开箱即用包交付。** 构建需在有 Docker 的联网维护者机器执行。最终用户获得构建后的整个项目，离线机器不需下载依赖、不需 Docker。

```bash
bash scripts/build-offline.sh ubuntu-24.04-amd64
bash scripts/build-offline.sh centos-8.5-x86_64
```

脚本把系统依赖闭包、所有 Python wheels、pip 引导包、tcping、版本清单和 SHA256 写入本目录的平台子目录，再启动干净且断网的容器验证首次安装、重复安装及测试。通过后才创建 VALIDATED。发布时携带完整项目，包括这些二进制文件，不应只发布脚本、Git LFS 指针或下载链接。

目标机器（root）：

```bash
bash install.sh
```

仅使用项目内依赖；安装失败不会尝试联网。会安装缺失系统包并可能更新它们的依赖，不修改系统软件源，不使用 --nodeps，不覆盖配置，不创建 cron、不启动采集。不同的已有 tcping 会导致明确报错。

系统包版本在 Ubuntu 更新仓库变化后可能不同，构建时生成的 manifest/requirements.lock 才是该包的实际版本；必须同时保留构建日志及基础镜像版本。CentOS 8.5 使用归档源，较早 8.x 系统需先在克隆环境验证本地依赖升级。

CentOS 构建基础镜像使用官方 Quay `centos8` 标签对应的固定摘要，系统包从 8.5.2111 归档下载，不依赖不存在的 `centos8.5.2111` 镜像标签。tcping 版本检查使用内置 2.6.0 支持的 `-v`。构建中断且未生成 VALIDATED 时可保留下载文件，修复后重新运行同一构建命令。

SHA256 检测传输损坏，不替代发布来源认证。VALIDATED 是构建流程的验收记录，不是第三方认证。

`bundle.meta`（格式版本、平台、Python 版本）与 `SHA256SUMS` 是安装前可在无 Python 主机上检查的权威清单；`manifest.json` 是供维护者查看的辅助报告。所有安装所需文件先通过独立 `scripts/check-bundle.sh` 检查，再调用系统包管理器。

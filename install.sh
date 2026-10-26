#!/usr/bin/env bash
# Offline by default. No network downloads, cron changes or agent startup.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
die() { printf '安装失败：%s\n' "$*" >&2; exit 1; }
if [[ ${1:-} == --help ]]; then
    printf '用法：bash install.sh [--bundle 离线包目录] [--config 配置文件]\n默认使用项目 offline/<当前平台> 内的完整离线包，不访问网络。\n'
    exit 0
fi
BUNDLE=''
CONFIG=''
while (($#)); do
    case "$1" in
        --bundle|--config)
            (($# >= 2)) || die "$1 缺少参数"
            if [[ $1 == --bundle ]]; then BUNDLE=$2; else CONFIG=$2; fi
            shift 2 ;;
        *) die "未知参数 $1；请运行 bash install.sh --help" ;;
    esac
done
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || die '仅支持 Linux x86_64'
[[ -r /etc/os-release ]] || die '无法读取系统信息'
# os-release is supplied by the operating system, never by the bundle.
source /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
    ubuntu:24.04) PROFILE=ubuntu-24.04-amd64; PYTHON=python3.12; PACKAGES=debs ;;
    centos:8|centos:8.5)
        [[ ${NAME:-} != *Stream* ]] || die 'CentOS Stream 不适用 CentOS Linux 离线包'
        PROFILE=centos-8.5-x86_64; PYTHON=python3.9; PACKAGES=rpms ;;
    *) die '仅支持 Ubuntu 24.04 和 CentOS Linux 8.5' ;;
esac
BUNDLE=${BUNDLE:-"$ROOT/offline/$PROFILE"}
bash "$ROOT/scripts/check-bundle.sh" "$BUNDLE" "$PROFILE"
BUNDLE=$(cd -- "$BUNDLE" && pwd)
pip_wheels=("$BUNDLE"/wheels/pip-*.whl)
[[ $EUID -eq 0 ]] || die '安装系统依赖需 root，请使用 sudo bash install.sh'
printf '正在安装 %s 的本地系统依赖……\n' "$PROFILE"
shopt -s nullglob
if [[ $PACKAGES == debs ]]; then
    packages=("$BUNDLE"/debs/*.deb)
    ((${#packages[@]})) || die '缺少 deb 软件包'
    # --no-download forbids network fetching even with configured remote sources.
    DEBIAN_FRONTEND=noninteractive apt-get --no-download --no-install-recommends -y install "${packages[@]}"
else
    packages=("$BUNDLE"/rpms/*.rpm)
    ((${#packages[@]})) || die '缺少 rpm 软件包'
    dnf --disablerepo='*' --setopt=install_weak_deps=False -y install "${packages[@]}"
fi
"$PYTHON" -m venv --without-pip "$ROOT/.venv" || die '虚拟环境创建失败'
VENV="$ROOT/.venv/bin/python"
# Bootstrap from the bundled wheel, including half-created venvs without pip.
PYTHONPATH="${pip_wheels[0]}" "$VENV" -m pip --isolated install --no-index --no-deps --disable-pip-version-check --force-reinstall "${pip_wheels[0]}"
"$VENV" -m pip --isolated install --no-index --only-binary=:all: --disable-pip-version-check --find-links "$BUNDLE/wheels" -r "$BUNDLE/requirements.lock"
"$VENV" -m pip --isolated check
"$VENV" -c 'import psutil, pyzabbix, yaml; print("Python 依赖检查通过")'
if [[ -e /usr/local/sbin/tcping || -L /usr/local/sbin/tcping ]]; then
    cmp -s "$BUNDLE/bin/tcping" /usr/local/sbin/tcping || die '已有不同的 /usr/local/sbin/tcping，未覆盖；请先检查该文件'
else
    install -m 0755 "$BUNDLE/bin/tcping" /usr/local/sbin/tcping
fi
chmod +x /usr/local/sbin/tcping
command -v ping >/dev/null && command -v ip >/dev/null || die '缺少 ping/ip'
bash "$ROOT/scripts/check-tcping.sh" /usr/local/sbin/tcping || die 'tcping 无法执行，请检查平台和共享库'
if [[ -n $CONFIG ]]; then
    "$VENV" "$ROOT/start.py" --config "$CONFIG" --check-config
else
    "$VENV" "$ROOT/start.py" --check-config
fi
printf '\n安装完成。未启动采集，也未添加 cron。请核对配置后执行：\n  %q %q\n' "$VENV" "$ROOT/start.py"

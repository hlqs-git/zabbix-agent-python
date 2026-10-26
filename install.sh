#!/usr/bin/env bash
# Install only application dependencies. Never call apt/dnf or access the network.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
die() { printf '安装失败：%s\n' "$*" >&2; exit 1; }
if [[ ${1:-} == --help ]]; then
    printf '用法：bash install.sh [--bundle 离线目录] [--config 配置文件]\n系统 Python/venv/ping/ip 需预先安装，脚本只离线安装 Python 库和项目内 tcping。\n'
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
source /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
    ubuntu:24.04)
        PROFILE=ubuntu-24.04-amd64; PYTHON=python3.12; PYTHON_VERSION=3.12
        PREREQUISITES='apt-get install -y python3.12 python3.12-venv iputils-ping iproute2 ca-certificates' ;;
    centos:8|centos:8.5)
        [[ ${NAME:-} != *Stream* ]] || die 'CentOS Stream 不适用 CentOS Linux 离线包'
        PROFILE=centos-8.5-x86_64; PYTHON=python3.9; PYTHON_VERSION=3.9
        PREREQUISITES='dnf install -y python39 python39-pip iputils iproute ca-certificates' ;;
    *) die '仅支持 Ubuntu 24.04 和 CentOS Linux 8.5' ;;
esac
missing=()
for tool in "$PYTHON" ping ip; do
    command -v "$tool" >/dev/null || missing+=("$tool")
done
if ((${#missing[@]})); then
    printf '缺少基础工具：%s\n请由管理员通过系统源或内网软件源预装：\n  %s\n' "${missing[*]}" "$PREREQUISITES" >&2
    exit 1
fi
"$PYTHON" -c 'import venv' || die "缺少 venv，请预装：$PREREQUISITES"
BUNDLE=${BUNDLE:-"$ROOT/offline/$PROFILE"}
bash "$ROOT/scripts/check-bundle.sh" "$BUNDLE" "$PROFILE" "$PYTHON" "$ROOT/package/download/tcping"
BUNDLE=$(cd -- "$BUNDLE" && pwd)
if [[ -e "$ROOT/.venv/pyvenv.cfg" ]]; then
    # Preserve existing environments for another interpreter instead of modifying them.
    "$PYTHON" - "$ROOT/.venv/pyvenv.cfg" "$PYTHON_VERSION" <<'PY'
from pathlib import Path
import sys
lines = dict(line.split('=', 1) for line in Path(sys.argv[1]).read_text().splitlines() if '=' in line)
version = lines.get('version ', lines.get('version', '')).strip()
if version and not version.startswith(sys.argv[2] + '.'):
    raise SystemExit('已有 .venv 使用不同 Python 版本；请先备份并移出该目录再安装。')
PY
fi
"$PYTHON" -m venv --without-pip "$ROOT/.venv"
VENV="$ROOT/.venv/bin/python"
shopt -s nullglob
pip_wheels=("$BUNDLE"/wheels/pip-*.whl)
[[ ${#pip_wheels[@]} == 1 ]] || die '需要且只能有一个 pip 引导 wheel'
PYTHONPATH="${pip_wheels[0]}" "$VENV" -m pip --isolated install --no-index --no-deps --disable-pip-version-check --force-reinstall "${pip_wheels[0]}"
"$VENV" -m pip --isolated install --no-index --only-binary=:all: --disable-pip-version-check --find-links "$BUNDLE/wheels" -r "$BUNDLE/requirements.lock"
"$VENV" -m pip --isolated check
"$VENV" -c 'import psutil, pyzabbix, yaml; print("Python 依赖检查通过")'
# One shared source binary in the project; runtime copy stays inside ignored .venv.
"$VENV" - "$ROOT/package/download/tcping" "$ROOT/.venv/bin/tcping" <<'PY'
from pathlib import Path
import shutil
import sys
shutil.copyfile(sys.argv[1], sys.argv[2])
Path(sys.argv[2]).chmod(0o755)
PY
bash "$ROOT/scripts/check-tcping.sh" "$ROOT/.venv/bin/tcping"
if [[ -n $CONFIG ]]; then
    "$VENV" "$ROOT/start.py" --config "$CONFIG" --check-config
else
    "$VENV" "$ROOT/start.py" --check-config
fi
printf '\n安装完成。配置未覆盖，未启动采集、未添加 cron。\n执行：%q %q\n' "$VENV" "$ROOT/start.py"

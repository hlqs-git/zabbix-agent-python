#!/usr/bin/env bash
# Maintainer-only: run on a networked Docker host; target machines need no Docker.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PROFILE=${1:-}
case "$PROFILE" in
    ubuntu-24.04-amd64) IMAGE=ubuntu:24.04 ;;
    centos-8.5-x86_64) IMAGE=quay.io/centos/centos:centos8.5.2111 ;;
    *) echo '用法：bash scripts/build-offline.sh ubuntu-24.04-amd64|centos-8.5-x86_64' >&2; exit 2 ;;
esac
command -v docker >/dev/null || { echo '构建需要联网的 Docker 主机；目标安装主机不需要 Docker。' >&2; exit 1; }
OUTPUT="$ROOT/offline/$PROFILE"
mkdir -p "$OUTPUT"
[[ ! -e "$OUTPUT/VALIDATED" ]] || { echo '已有验收完成的离线包，请先备份并移出后再构建。' >&2; exit 1; }
docker run --rm --platform linux/amd64 -e PROFILE="$PROFILE" -v "$ROOT:/project:ro" -v "$OUTPUT:/output" "$IMAGE" bash /project/scripts/build-offline-container.sh
# Start a separate pristine image without network. Test first install AND repair.
docker run --rm --network none --platform linux/amd64 -e PROFILE="$PROFILE" -v "$ROOT:/source:ro" "$IMAGE" bash -c '
set -euo pipefail
mkdir /project
tar -C /source --exclude=.git --exclude=.venv --exclude=log -cf - . | tar -C /project -xf -
cd /project
INSTALL_BUILD_TEST=1 bash /project/install.sh
INSTALL_BUILD_TEST=1 bash /project/install.sh
/project/.venv/bin/python -m unittest discover -s /project/tests -v
'
printf 'Offline installation verified in %s with network disabled.\n' "$IMAGE" > "$OUTPUT/VALIDATED"
echo "完整离线包已写入 $OUTPUT，请将整个项目目录一起发布。"

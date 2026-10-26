#!/usr/bin/env bash
# Optional maintainer validation; preparing lightweight bundles needs no Docker.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PROFILE=${1:-}
case "$PROFILE" in
    ubuntu-24.04-amd64) IMAGE=ubuntu:24.04 ;;
    centos-8.5-x86_64) IMAGE=quay.io/centos/centos@sha256:8301d100020ffaedc93f57d8c8bb0e8e88006862bcb48ebc5dfbe1d1cb83060c ;;
    *) echo '用法：bash scripts/validate-offline.sh ubuntu-24.04-amd64|centos-8.5-x86_64' >&2; exit 2 ;;
esac
TAG="zabbix-agent-offline-test:$PROFILE"
# Only this stage is online; it models the documented preinstalled prerequisites.
docker build --platform linux/amd64 --build-arg BASE_IMAGE="$IMAGE" --build-arg PROFILE="$PROFILE" -t "$TAG" -f "$ROOT/scripts/offline-test.Dockerfile" "$ROOT/scripts"
docker run --rm --network none --platform linux/amd64 -v "$ROOT:/source:ro" "$TAG" bash -c '
set -euo pipefail
mkdir /project
tar -C /source --exclude=.git --exclude=.venv --exclude=log -cf - . | tar -C /project -xf -
cd /project
bash install.sh
bash install.sh
/project/.venv/bin/python -m unittest discover -s tests -v
'
printf 'Application installation tested with network disabled; OS prerequisites preinstalled.\n' > "$ROOT/offline/$PROFILE/VALIDATED"
echo '轻量应用离线安装验收通过。'

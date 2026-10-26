#!/usr/bin/env bash
# Maintainer preparation: Python wheels only. No Docker/system package downloads.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# -lt 1 ]]; then
    echo '用法：bash scripts/build-offline.sh ubuntu-24.04-amd64|centos-8.5-x86_64 [--seal-only]' >&2
    exit 2
fi
PYTHON=${PYTHON:-python3}
"$PYTHON" "$ROOT/scripts/prepare-wheels.py" "$@"

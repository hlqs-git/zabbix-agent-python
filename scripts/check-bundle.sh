#!/usr/bin/env bash
# Python is now an explicit system prerequisite. No cmp/find/sort dependency.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
BUNDLE=${1:?bundle directory is required}
PROFILE=${2:?profile is required}
PYTHON=${3:-python3}
TCPING=${4:-"$ROOT/package/download/tcping"}
"$PYTHON" "$ROOT/scripts/bundle.py" verify "$BUNDLE" "$PROFILE" --tcping "$TCPING"

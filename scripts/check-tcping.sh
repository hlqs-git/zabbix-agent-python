#!/usr/bin/env bash
# The bundled tcping 2.6.0 supports -v, not --version.
set -euo pipefail
BINARY=${1:?tcping path is required}
if ! version=$("$BINARY" -v 2>&1); then
    printf 'tcping 版本检查失败：%s\n%s\n' "$BINARY" "$version" >&2
    exit 1
fi
[[ $version == *'TCPING version '* ]] || {
    printf '无法识别 tcping 版本输出：%s\n' "$version" >&2
    exit 1
}
printf '%s\n' "$version"

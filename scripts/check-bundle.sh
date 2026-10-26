#!/usr/bin/env bash
# Validate an offline payload before any package manager or system change.
set -euo pipefail
BUNDLE=${1:?bundle directory is required}
PROFILE=${2:?profile is required}
die() { printf '离线包检查失败：%s\n' "$*" >&2; exit 1; }
[[ -f "$BUNDLE/SHA256SUMS" && -f "$BUNDLE/bundle.meta" ]] || die "离线包不完整：$BUNDLE；需要维护者先完成构建，不能在离线主机补下载"
[[ -f "$BUNDLE/VALIDATED" ]] || [[ ${INSTALL_BUILD_TEST:-0} == 1 ]] || die '该离线包尚未完成断网验收，不能作为完整安装包使用'
command -v sha256sum >/dev/null || die '缺少 sha256sum'
BUNDLE=$(cd -- "$BUNDLE" && pwd)
if find "$BUNDLE" -type l -print -quit | grep -q .; then die '离线包不能包含符号链接'; fi
while IFS= read -r line; do
    [[ $line =~ ^[0-9a-f]{64}\ \ [A-Za-z0-9][A-Za-z0-9._+/%-]*$ ]] || die '非法校验清单记录'
    name=${line:66}
    [[ /$name/ != */../* && /$name/ != */./* ]] || die '非法校验文件路径'
done < "$BUNDLE/SHA256SUMS"
inventory_tmp=$(mktemp -d)
trap 'rm -f "$inventory_tmp/actual" "$inventory_tmp/expected"; rmdir "$inventory_tmp"' EXIT
(cd -- "$BUNDLE" && find . -type f ! -name SHA256SUMS ! -name VALIDATED -printf '%P\n' | LC_ALL=C sort) > "$inventory_tmp/actual"
cut -c67- "$BUNDLE/SHA256SUMS" | LC_ALL=C sort > "$inventory_tmp/expected"
cmp -s "$inventory_tmp/actual" "$inventory_tmp/expected" || die '离线包包含缺失或未登记文件'
(cd -- "$BUNDLE" && sha256sum --check --strict SHA256SUMS) || die '离线包完整性校验失败'
# bundle.meta + SHA256SUMS are the authoritative bootstrap manifest, readable
# without Python. manifest.json is an informational copy for maintainers.
expected_python=3.12
[[ $PROFILE != centos-8.5-x86_64 ]] || expected_python=3.9
[[ $(cat "$BUNDLE/bundle.meta") == "1 $PROFILE $expected_python" ]] || die '不支持的离线包格式或平台/Python 不匹配'
[[ -s "$BUNDLE/requirements.lock" && -s "$BUNDLE/bin/tcping" ]] || die '缺少锁定依赖清单或 tcping'
pip_wheels=("$BUNDLE"/wheels/pip-*.whl)
[[ ${#pip_wheels[@]} == 1 && -f ${pip_wheels[0]} ]] || die '需要且只能有一个 pip 引导 wheel'
for package_prefix in psutil py_zabbix PyYAML; do
    matched=("$BUNDLE"/wheels/"$package_prefix"-*.whl)
    [[ ${#matched[@]} == 1 && -f ${matched[0]} ]] || die "缺少或重复的 Python wheel: $package_prefix"
done

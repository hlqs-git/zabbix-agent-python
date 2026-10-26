#!/usr/bin/env bash
set -euo pipefail
# Only the disposable build container uses UTC; target host timezone is untouched.
export DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC
[[ -n ${PROFILE:-} && -d /output && -d /project ]] || { echo '请通过 build-offline.sh 调用' >&2; exit 2; }
mkdir -p /output/wheels /output/bin
case "$PROFILE" in
    ubuntu-24.04-amd64)
        apt-get update
        mkdir -p /output/debs/partial
        touch /tmp/empty-status
        # Empty status makes apt include dependencies already present in the build image.
        apt-get -y --download-only --no-install-recommends -o Dir::State::status=/tmp/empty-status -o Dir::Cache::archives=/output/debs install python3.12 python3.12-venv iputils-ping iproute2 ca-certificates
        apt-get -y --no-install-recommends install python3.12 python3.12-venv ca-certificates
        PYTHON=python3.12 ;;
    centos-8.5-x86_64)
        mkdir /tmp/original-repos
        mv /etc/yum.repos.d/*.repo /tmp/original-repos/
        cat > /etc/yum.repos.d/offline-build.repo <<'REPO'
[baseos]
name=CentOS Linux 8.5 BaseOS archive
baseurl=https://vault.centos.org/8.5.2111/BaseOS/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial
[appstream]
name=CentOS Linux 8.5 AppStream archive
baseurl=https://vault.centos.org/8.5.2111/AppStream/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial
REPO
        dnf -y install dnf-plugins-core
        mkdir -p /output/rpms
        dnf download --resolve --alldeps --destdir /output/rpms python39 python39-pip iputils iproute ca-certificates
        dnf -y install python39 python39-pip ca-certificates
        PYTHON=python3.9 ;;
    *) exit 2 ;;
esac
"$PYTHON" -m venv /tmp/build-venv
BUILD_PYTHON=/tmp/build-venv/bin/python
"$BUILD_PYTHON" -m pip install 'pip==25.1.1'
"$BUILD_PYTHON" -m pip download --only-binary=:all: --dest /output/wheels -r /project/offline/requirements.in 'pip==25.1.1'
"$BUILD_PYTHON" -m pip install --no-index --find-links /output/wheels -r /project/offline/requirements.in
"$BUILD_PYTHON" -m pip freeze > /output/requirements.lock
install -m 0755 /project/package/download/tcping /output/bin/tcping
bash /project/scripts/check-tcping.sh /output/bin/tcping
find /output -type d -empty -delete
rm -f /output/debs/lock
"$BUILD_PYTHON" /project/scripts/bundle.py seal /output "$PROFILE"

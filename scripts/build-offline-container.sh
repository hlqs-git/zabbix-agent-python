#!/usr/bin/env bash
# Validation image setup only: preinstall documented OS prerequisites.
# No system packages are copied into project/offline.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC
case "${PROFILE:?profile is required}" in
    ubuntu-24.04-amd64)
        apt-get update
        apt-get -y --no-install-recommends install python3.12 python3.12-venv iputils-ping iproute2 ca-certificates
        ;;
    centos-8.5-x86_64)
        mkdir /tmp/original-repos
        mv /etc/yum.repos.d/*.repo /tmp/original-repos/
        cat > /etc/yum.repos.d/offline-test.repo <<'REPO'
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
        dnf -y install python39 python39-pip iputils iproute ca-certificates
        ;;
    *) exit 2 ;;
esac

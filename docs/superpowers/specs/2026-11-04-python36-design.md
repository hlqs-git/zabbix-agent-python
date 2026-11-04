# CentOS 8.5 / Python 3.6 support

Approved by the user in chat. Support CentOS Linux release 8.5.2111 x86_64
with Python 3.6.8; retain Ubuntu 24.04 / Python 3.12.

Use the dataclasses backport, Python-3.6 subprocess arguments, and separate
CentOS wheel pins (pip 21.3.1, PyYAML 6.0, dataclasses 0.8).
Keep psutil 5.9.8 and py-zabbix 1.1.7. Update installation, preparation,
checksums, tests and documentation together. Preserve configuration and metrics.

Keeping Python 3.9 would not satisfy the requested interpreter. Replacing
dataclasses throughout the application would add unnecessary behavior changes.
Validate locally and with a real Python 3.6 interpreter if available; distinguish
these checks from a complete CentOS offline installation.

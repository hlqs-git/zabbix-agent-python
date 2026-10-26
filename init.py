"""Compatibility entry point for the unified offline Linux installer."""
from pathlib import Path
import subprocess
import sys


def main():
    if not sys.platform.startswith('linux'):
        print('安装需要 Linux；请在目标主机执行 bash install.sh', file=sys.stderr)
        return 2
    installer = Path(__file__).resolve().with_name('install.sh')
    return subprocess.call(['bash', str(installer)] + sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())

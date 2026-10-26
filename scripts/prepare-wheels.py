"""Maintainer helper: download Linux wheels from Windows or Linux.

This prepares Python dependencies only. It never marks a system bundle ready.
Complete system payloads must be built and tested with build-offline.sh.
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {'ubuntu-24.04-amd64': ('3.12', 'cp312'), 'centos-8.5-x86_64': ('3.9', 'cp39')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=VERSIONS)
    args = parser.parse_args()
    version, abi = VERSIONS[args.profile]
    target = ROOT / 'offline' / args.profile / 'wheels'
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
                    '--platform', 'manylinux2014_x86_64', '--python-version', version,
                    '--implementation', 'cp', '--abi', abi, '--abi', 'abi3', '--abi', 'none',
                    '--dest', str(target), '--timeout', '20', '--retries', '1',
                    '-r', str(ROOT / 'offline/requirements.in'), 'pip==25.1.1'], check=True)


if __name__ == '__main__':
    main()

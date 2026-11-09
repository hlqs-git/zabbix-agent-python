"""Maintainer helper: download Linux wheels from Windows or Linux.

System packages are prerequisites documented separately. Shared tcping is
already stored in package/download/tcping and covered by each manifest.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import zipfile
from email.parser import BytesParser

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {'ubuntu-24.04-amd64': ('3.12', 'cp312'), 'centos-8.5-x86_64': ('3.6', 'cp36m')}

VERSIONS.update({'python-3.{}-x86_64'.format(m): ('3.{}'.format(m), 'cp3{}{}'.format(m, 'm' if m < 8 else '')) for m in range(6, 13)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=VERSIONS)
    parser.add_argument('--seal-only', action='store_true', help='Use already downloaded wheels without network access')
    args = parser.parse_args()
    version, abi = VERSIONS[args.profile]
    target = ROOT / 'offline' / args.profile / 'wheels'
    target.mkdir(parents=True, exist_ok=True)
    requirements = ROOT / 'offline' / ('requirements-centos36.in' if version == '3.6' else ('requirements-python37.in' if version == '3.7' else 'requirements.in'))
    pip_version = {'3.6': '21.3.1', '3.7': '24.0', '3.8': '25.0.1'}.get(version, '25.1.1')
    if not args.seal_only:
        subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:',
                    '--platform', 'manylinux2014_x86_64', '--python-version', version,
                    '--implementation', 'cp', '--abi', abi, '--abi', 'abi3', '--abi', 'none',
                    '--dest', str(target), '--timeout', '20', '--retries', '1',
                        '-r', str(requirements), 'pip==' + pip_version], check=True)
    pins = {}
    for wheel in sorted(target.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            metadata_paths = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
            if len(metadata_paths) != 1:
                raise ValueError('Invalid wheel metadata: ' + wheel.name)
            metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
            name, release = metadata['Name'], metadata['Version']
            key = name.lower().replace('_', '-')
            if key in pins:
                raise ValueError('Duplicate wheel distribution: ' + name)
            pins[key] = (name, release)
    required = {'pip', 'psutil', 'py-zabbix', 'pyyaml'}
    if version == '3.6':
        required.add('dataclasses')
    if not required.issubset(pins):
        raise ValueError('Missing wheels: ' + ', '.join(sorted(required - pins.keys())))
    from bundle import seal, write_text
    write_text(target.parent / 'requirements.lock', ''.join('{}=={}\n'.format(*pins[key]) for key in sorted(pins) if key != 'pip'))
    seal(target.parent, args.profile)
    print('Lightweight bundle prepared: ' + str(target.parent))


if __name__ == '__main__':
    main()

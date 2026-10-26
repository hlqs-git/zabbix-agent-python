"""Offline payload inventory. Standard library only, no network access."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

PROFILES = {
    'ubuntu-24.04-amd64': ('debs', '.deb', '3.12'),
    'centos-8.5-x86_64': ('rpms', '.rpm', '3.9'),
}


def write_text(path, text):
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)


def detect_platform(info, arch):
    if arch != 'x86_64':
        raise ValueError('Only amd64/x86_64 is supported')
    if info.get('ID') == 'ubuntu' and info.get('VERSION_ID') == '24.04':
        return 'ubuntu-24.04-amd64'
    if info.get('ID') == 'centos' and info.get('VERSION_ID') in ('8', '8.5') and 'Stream' not in info.get('NAME', ''):
        return 'centos-8.5-x86_64'
    raise ValueError('Supported systems: Ubuntu 24.04 and CentOS Linux 8.5 (not Stream)')


def inventory(root):
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are not allowed in the bundle: {}'.format(path))
        name = path.relative_to(root).as_posix()
        if path.is_file() and name not in ('manifest.json', 'SHA256SUMS', 'VALIDATED'):
            if any(c.isspace() for c in name) or '\\' in name:
                raise ValueError('Unsafe payload filename: {}'.format(name))
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def seal(root, profile):
    directory, extension, python = PROFILES[profile]
    write_text(root / 'bundle.meta', '1 {} {}\n'.format(profile, python))
    files = inventory(root)
    if not any(name.startswith(directory + '/') and name.endswith(extension) for name in files):
        raise ValueError('Missing system packages for {}'.format(profile))
    for prefix in ('pip-', 'psutil-', 'py_zabbix-', 'pyyaml-'):
        if not any(name.lower().startswith('wheels/' + prefix) and name.endswith('.whl') for name in files):
            raise ValueError('Missing wheel: ' + prefix)
    if 'bin/tcping' not in files or 'requirements.lock' not in files:
        raise ValueError('Missing tcping or requirements.lock')
    manifest = {'schema': 1, 'profile': profile, 'python': python, 'files': files}
    write_text(root / 'manifest.json', json.dumps(manifest, indent=2) + '\n')
    files['manifest.json'] = hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest()
    write_text(root / 'SHA256SUMS', ''.join('{}  {}\n'.format(digest, name) for name, digest in sorted(files.items())))


def verify(root, profile):
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1 or manifest.get('profile') != profile:
        raise ValueError('Bundle platform/schema mismatch')
    if inventory(root) != manifest['files']:
        raise ValueError('Bundle missing, extra or modified files')
    if (root / 'bundle.meta').read_text(encoding='utf-8') != '1 {} {}\n'.format(profile, PROFILES[profile][2]):
        raise ValueError('Unsupported bundle metadata')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('seal', 'verify', 'detect'))
    parser.add_argument('root', nargs='?', type=Path)
    parser.add_argument('profile', nargs='?', choices=PROFILES)
    args = parser.parse_args()
    if args.action == 'detect':
        info = {}
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                info[key] = value.strip('"')
        print(detect_platform(info, platform.machine()))
    elif args.root is None or args.profile is None:
        parser.error('root and profile are required')
    else:
        {'seal': seal, 'verify': verify}[args.action](args.root, args.profile)


if __name__ == '__main__':
    main()

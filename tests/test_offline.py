import importlib.util
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class OfflineTests(unittest.TestCase):
    def test_tcping_version_check_uses_supported_flag(self):
        bash = shutil.which('bash') or ('C:/Workspace/App/Git/bin/bash.exe' if Path('C:/Workspace/App/Git/bin/bash.exe').exists() else None)
        if not bash:
            self.skipTest('Bash unavailable')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'tcping'
            target.write_text('#!/usr/bin/env bash\nif [[ $1 != -v ]]; then exit 2; fi\necho "TCPING version 2.6.0"\n', encoding='utf-8')
            target.chmod(0o755)
            command = [bash, str(ROOT / 'scripts/check-tcping.sh'), str(target)]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            target.write_text('#!/usr/bin/env bash\nexit 2\n', encoding='utf-8')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_shell_preflight_rejects_missing_and_wrong_schema(self):
        bash = shutil.which('bash') or ('C:/Workspace/App/Git/bin/bash.exe' if Path('C:/Workspace/App/Git/bin/bash.exe').exists() else None)
        if not bash:
            self.skipTest('Bash unavailable')
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [bash, str(ROOT / 'scripts/check-bundle.sh'), str(root), 'ubuntu-24.04-amd64']
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            for name in ('debs/python.deb', 'wheels/pip-1-py3-none-any.whl', 'wheels/psutil-1.whl', 'wheels/py_zabbix-1.whl', 'wheels/PyYAML-1.whl', 'bin/tcping', 'requirements.lock'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'payload')
            module.seal(root, 'ubuntu-24.04-amd64')
            (root / 'VALIDATED').write_text('test fixture', encoding='utf-8')
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            # Recompute checksums so a valid checksum cannot hide an unsupported schema.
            module.write_text(root / 'bundle.meta', '2 ubuntu-24.04-amd64 3.12\n')
            import hashlib
            lines = []
            for line in (root / 'SHA256SUMS').read_text().splitlines():
                name = line[66:]
                lines.append(hashlib.sha256((root / name).read_bytes()).hexdigest() + '  ' + name)
            module.write_text(root / 'SHA256SUMS', '\n'.join(lines) + '\n')
            rejected = subprocess.run(command, capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('不支持', rejected.stderr.decode('utf-8'))

    def module(self):
        spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_profiles(self):
        module = self.module()
        self.assertEqual(module.detect_platform({'ID': 'ubuntu', 'VERSION_ID': '24.04'}, 'x86_64'), 'ubuntu-24.04-amd64')
        self.assertEqual(module.detect_platform({'ID': 'centos', 'VERSION_ID': '8.5', 'NAME': 'CentOS Linux'}, 'x86_64'), 'centos-8.5-x86_64')
        for info, arch in [({'ID': 'ubuntu', 'VERSION_ID': '22.04'}, 'x86_64'), ({'ID': 'centos', 'VERSION_ID': '8', 'NAME': 'CentOS Stream'}, 'x86_64'), ({'ID': 'ubuntu', 'VERSION_ID': '24.04'}, 'aarch64')]:
            with self.assertRaises(ValueError):
                module.detect_platform(info, arch)

    def test_seal_requires_complete_payload(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                module.seal(Path(directory), 'ubuntu-24.04-amd64')

    def test_manifest_detects_tampering_and_extra_files(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('debs/python.deb', 'wheels/pip-1-py3-none-any.whl', 'wheels/psutil-1.whl', 'wheels/py_zabbix-1.whl', 'wheels/PyYAML-1.whl', 'bin/tcping', 'requirements.lock'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'payload')
            module.seal(root, 'ubuntu-24.04-amd64')
            module.verify(root, 'ubuntu-24.04-amd64')
            with self.assertRaises(ValueError):
                module.verify(root, 'centos-8.5-x86_64')
            (root / 'bin/tcping').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                module.verify(root, 'ubuntu-24.04-amd64')
            (root / 'bin/tcping').write_bytes(b'payload')
            (root / 'debs/extra.deb').write_bytes(b'not registered')
            with self.assertRaises(ValueError):
                module.verify(root, 'ubuntu-24.04-amd64')

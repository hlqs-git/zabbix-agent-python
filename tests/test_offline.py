import importlib.util
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def bash_path():
    return shutil.which('bash') or ('C:/Workspace/App/Git/bin/bash.exe' if Path('C:/Workspace/App/Git/bin/bash.exe').exists() else None)


class OfflineTests(unittest.TestCase):
    def fixture(self, base):
        root = base / 'offline/ubuntu-24.04-amd64'
        for name in ('wheels/pip-1.whl', 'wheels/psutil-1.whl', 'wheels/py_zabbix-1.whl', 'wheels/PyYAML-1.whl', 'requirements.lock'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'payload')
        binary = base / 'package/download/tcping'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b'tcping')
        return root, binary

    def test_tcping_version_check_uses_supported_flag(self):
        bash = bash_path()
        if not bash:
            self.skipTest('Bash unavailable')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'tcping'
            self.module().write_text(target, '#!/usr/bin/env bash\nif [[ $1 != -v ]]; then exit 2; fi\necho "TCPING version 2.6.0"\n')
            target.chmod(0o755)
            command = [bash, str(ROOT / 'scripts/check-tcping.sh'), str(target)]
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.module().write_text(target, '#!/usr/bin/env bash\nexit 2\n')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_shell_preflight_rejects_missing_and_wrong_schema(self):
        bash = bash_path()
        if not bash:
            self.skipTest('Bash unavailable')
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root, binary = self.fixture(Path(directory))
            command = [bash, str(ROOT / 'scripts/check-bundle.sh'), str(root), 'ubuntu-24.04-amd64', sys.executable, str(binary)]
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            module.seal(root, 'ubuntu-24.04-amd64')
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            import json
            manifest_path = root / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['schema'] = 99
            module.write_text(manifest_path, json.dumps(manifest))
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

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
            root, binary = self.fixture(Path(directory))
            module.seal(root, 'ubuntu-24.04-amd64')
            module.verify(root, 'ubuntu-24.04-amd64')
            with self.assertRaises(ValueError):
                module.verify(root, 'centos-8.5-x86_64')
            binary.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                module.verify(root, 'ubuntu-24.04-amd64')
            binary.write_bytes(b'tcping')
            (root / 'wheels/extra.whl').write_bytes(b'not registered')
            with self.assertRaises(ValueError):
                module.verify(root, 'ubuntu-24.04-amd64')

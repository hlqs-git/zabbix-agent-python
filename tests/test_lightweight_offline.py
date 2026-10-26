import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from agent.collectors.tcp import tcping

ROOT = Path(__file__).resolve().parents[1]


class LightweightTests(unittest.TestCase):
    def test_relocated_bundle_verifies_the_binary_actually_installed(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, binary = self.fixture(base)
            module.seal(root, 'ubuntu-24.04-amd64')
            moved = base / 'relocated'
            shutil.copytree(root, moved)
            module.verify(moved, 'ubuntu-24.04-amd64', tcping=binary)
            binary.write_bytes(b'corrupt actual install source')
            with self.assertRaises(ValueError):
                module.verify(moved, 'ubuntu-24.04-amd64', tcping=binary)

    def test_collector_uses_project_tcping_in_namespace(self):
        output = '{"type":"statistics","addr":"1.1.1.1","total_packet_loss":0,"latency_avg":1}'
        with patch('agent.collectors.tcp.Path.is_file', return_value=True), patch('agent.collectors.tcp.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=output, stderr='')) as run:
            self.assertEqual(tcping('1.1.1.1', 443, count=1, namespace='ns1'), ('1.1.1.1', 0.0, 1.0))
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ['ip', 'netns', 'exec', 'ns1'])
        self.assertEqual(Path(command[4]), ROOT / '.venv/bin/tcping')

    def module(self):
        spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

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

    def test_python_only_bundle_and_shared_tcping(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root, binary = self.fixture(Path(directory))
            module.seal(root, 'ubuntu-24.04-amd64')
            module.verify(root, 'ubuntu-24.04-amd64')
            binary.write_bytes(b'modified')
            with self.assertRaises(ValueError):
                module.verify(root, 'ubuntu-24.04-amd64')

    def test_no_system_packages_allowed(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root, binary = self.fixture(Path(directory))
            (root / 'debs').mkdir()
            (root / 'debs/package.deb').write_bytes(b'system package')
            with self.assertRaisesRegex(ValueError, 'system|系统'):
                module.seal(root, 'ubuntu-24.04-amd64')

    def test_preflight_needs_no_cmp_and_no_validation_marker(self):
        bash = shutil.which('bash') or ('C:/Workspace/App/Git/bin/bash.exe' if Path('C:/Workspace/App/Git/bin/bash.exe').exists() else None)
        if not bash:
            self.skipTest('Bash unavailable')
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root, binary = self.fixture(Path(directory))
            module.seal(root, 'ubuntu-24.04-amd64')
            result = subprocess.run([bash, str(ROOT / 'scripts/check-bundle.sh'), str(root), 'ubuntu-24.04-amd64', sys.executable, str(binary)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()

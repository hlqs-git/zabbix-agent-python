from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent.config import load_config
from agent.app import main
import warnings

BASE = 'zabbix:\n  server: zabbix.example.com\n  hostname: linux-01\n'


class YamlConfigTests(unittest.TestCase):
    def test_legacy_migration_preserves_metrics(self):
        root = Path(__file__).resolve().parents[1]
        with warnings.catch_warnings(record=True) as caught:
            legacy = load_config(root / 'conf/config.legacy.example.ini')
        self.assertTrue(any('INI' in str(w.message) for w in caught))
        migrated = self.load('''zabbix:
  server: 1.1.1.1
  hostname: hostname
system: true
interfaces:
  - device: ens5f0
ping:
  - address: 1.1.1.1
  - address: 8.8.8.8
tcp:
  - address: 1.1.1.1
    port: 80
    count: 50
  - address: 8.8.8.8
    port: 80
    count: 50
''')
        self.assertEqual(legacy, migrated)

    def test_default_selects_only_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'conf').mkdir()
            (root / 'conf/config.yml').write_text(BASE, encoding='utf-8')
            with patch('agent.config.ROOT', root):
                self.assertEqual(load_config().hostname, 'linux-01')

    def test_advanced_example_is_valid(self):
        root = Path(__file__).resolve().parents[1]
        cfg = load_config(root / 'conf/config.example.yaml')
        self.assertEqual(len(cfg.interfaces), 2)
        self.assertEqual(len(cfg.probes), 3)

    def load(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            path.write_text(content, encoding='utf-8')
            return load_config(path)

    def test_minimum_and_optional_targets(self):
        cfg = self.load(BASE)
        self.assertEqual((cfg.port, cfg.workers, cfg.system), (10051, 16, False))
        self.assertEqual(cfg.interfaces, [])
        self.assertEqual(cfg.probes, [])

    def test_targets_and_units(self):
        cfg = self.load(BASE + '''system: true
interfaces:
  - device: veth1
    namespace: ns1
    name: wan
ping:
  - address: 1.1.1.1
    duration_seconds: 3
tcp:
  - address: example.com
    port: 443
    name: web
    count: 4
    connect_timeout_seconds: 2
''')
        self.assertEqual(cfg.interfaces[0].namespace, 'ns1')
        self.assertEqual(cfg.interfaces[0].name, 'wan')
        self.assertEqual(cfg.probes[0].duration, 3)
        self.assertEqual((cfg.probes[1].name, cfg.probes[1].duration, cfg.probes[1].timeout), ('web:443', 4, 2))

    def test_actionable_errors(self):
        cases = [('tcp:\n  - address: example.com\n', 'tcp 第 1 个目标.port'),
                 ('system: "true"\n', 'system'),
                 ('ping:\n  - adress: 1.1.1.1\n', 'adress'),
                 ('ping: 1.1.1.1\n', '列表'),
                 ('runtime:\n  max_workers: true\n', '正整数'),
                 ('tcp:\n  - address: example.com\n    port: 70000\n', '65535'),
                 ('ping:\n  - address: 1.1.1.1\n  - address: 1.1.1.1\n', '重复'),
                 ('system: true\nsystem: false\n', '重复'),
                 ('system: true\nItem.sys: true\n', 'Item.sys'),
                 ('ping:\n  - address: ::1\n', 'IPv6')]
        cases.append(('ping:\n  - address: " -invalid"\n    name: safe\n', '不能以 -'))
        cases.append(('ping:\n  - address: 1.1.1.1\n    namespace: " -n"\n', '不能以 -'))
        for suffix, message in cases:
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, message):
                self.load(BASE + suffix)

    def test_syntax_and_unsafe_yaml(self):
        for content in ('[broken', '!!python/object/apply:os.system [echo unsafe]', '[]', ''):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.load(content)

    def test_default_ambiguity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'conf').mkdir()
            (root / 'conf/config.yaml').write_text(BASE, encoding='utf-8')
            (root / 'conf/config.ini').write_text('', encoding='utf-8')
            with patch('agent.config.ROOT', root), self.assertRaisesRegex(ValueError, '--config'):
                load_config()

    def test_summary_does_not_collect_or_send(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            path.write_text(BASE + 'ping:\n  - address: 1.1.1.1\n', encoding='utf-8')
            output = io.StringIO()
            with redirect_stdout(output), patch('agent.app.run_cycle') as cycle:
                self.assertEqual(main(['--config', str(path), '--check-config']), 0)
            cycle.assert_not_called()
            for value in ('linux-01', 'zabbix.example.com:10051', '1.1.1.1', '尚未连接'):
                self.assertIn(value, output.getvalue())


if __name__ == '__main__':
    unittest.main()

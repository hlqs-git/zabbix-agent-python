"""Regression checks for the oldest supported runtime."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUN = subprocess.run


class Python36Tests(unittest.TestCase):
    def test_collectors_use_python36_subprocess_api(self):
        from agent.collectors.icmp import ping
        from agent.collectors.network import get_ns_net_io_counters
        from agent.collectors.tcp import tcping

        def run36(command, **kwargs):
            self.assertNotIn('capture_output', kwargs)
            self.assertNotIn('text', kwargs)
            if command[0] == 'ping':
                output = '100% packet loss'
            elif '-j' in command and 'link' in command:
                output = json.dumps([{'stats64': {'rx': {'bytes': 1}, 'tx': {'bytes': 2}},
                                      'flags': ['UP', 'LOWER_UP']}])
            else:
                output = json.dumps({'type': 'statistics', 'addr': '127.0.0.1',
                                     'total_packet_loss': 0, 'latency_avg': 1})
            # Execute a real child process, with exactly the collector's arguments.
            return RUN([sys.executable, '-c', 'print({!r})'.format(output)], **kwargs)

        with patch('agent.collectors.command.subprocess.run', side_effect=run36):
            self.assertEqual(ping('127.0.0.1', sec=1), (100.0, 0.0))
            self.assertEqual(get_ns_net_io_counters('ns1', 'eth0'), (1, 2, 1))
            self.assertEqual(tcping('127.0.0.1', 443, count=1)[1:], (0.0, 1.0))

    def test_centos_bundle_requires_python36_and_dataclasses(self):
        spec = importlib.util.spec_from_file_location('bundle', ROOT / 'scripts/bundle.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.PROFILES['centos-8.5-x86_64'][2], '3.6')
        lock = (ROOT / 'offline/centos-8.5-x86_64/requirements.lock').read_text()
        self.assertIn('dataclasses==0.8', lock)
        module.verify(ROOT / 'offline/centos-8.5-x86_64', 'centos-8.5-x86_64')

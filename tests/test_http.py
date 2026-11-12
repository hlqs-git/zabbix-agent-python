import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.collectors.http import parse_httping, httping
from agent.yaml_config import parse_yaml, describe_config
from agent.app import probe_metrics
from agent.discovery import build_discovery

class HttpTests(unittest.TestCase):
    def test_statistics(self):
        self.assertEqual(parse_httping('10 connects, 8 ok, 20.00% failed, time 100ms\nround-trip min/avg/max = 1.0/2.5/4.0 ms'), (20.0, 2.5))
        self.assertEqual(parse_httping('10 connects, 0 ok, 100.00% failed, time 100ms'), (100.0, 0.0))
        for text in ('', '0% failed', '101% failed', '0% failed\nround-trip min/avg/max = 1/nan/2 ms'):
            with self.assertRaises(ValueError):
                parse_httping(text)

    def test_config_command_and_metrics(self):
        cfg = parse_yaml({'zabbix': {'server': 'server', 'hostname': 'host'}, 'http': [
            {'address': 'https://example.com/path', 'name': 'web', 'source_ip': '192.0.2.1', 'namespace': 'ns1', 'count': 2, 'timeout_seconds': 3}]})
        self.assertIn('HTTP', describe_config(cfg))
        self.assertIn('web', build_discovery(cfg)[1].value)
        with patch('agent.collectors.http.run_command', return_value=SimpleNamespace(returncode=0, stdout='0% failed\nround-trip min/avg/max = 1/2/3 ms', stderr='')) as run:
            metrics = probe_metrics('host', cfg.probes[0])
        self.assertEqual([(m.key, m.value) for m in metrics], [('ping_get[web,loss]', 0.0), ('ping_get[web,delay]', 2.0)])
        command = run.call_args[0][0]
        self.assertEqual(command[:4], ['ip', 'netns', 'exec', 'ns1'])
        self.assertEqual(command[command.index('-y') + 1], '192.0.2.1')
        self.assertIn('-l', command)
        self.assertIn('https://example.com/path', command)

    def test_invalid_configuration(self):
        for entry in ({'address': 'ftp://example.com'}, {'address': 'http://'}, {'address': 'example.com', 'source_ip': 'eth0'}, {'address': 'example.com', 'count': 0}):
            with self.assertRaises(ValueError):
                parse_yaml({'zabbix': {'server': 's', 'hostname': 'h'}, 'http': [entry]})

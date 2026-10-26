import unittest
from unittest.mock import patch
from types import SimpleNamespace

from agent.yaml_config import parse_yaml, describe_config
from agent.collectors.icmp import ping
from agent.app import probe_metrics


class PingSourceTests(unittest.TestCase):
    def test_default_command_has_no_source_override(self):
        with patch('agent.collectors.icmp.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='100% packet loss', stderr='')) as run:
            ping('1.1.1.1', 2)
        self.assertNotIn('-I', run.call_args.args[0])

    def config(self, source):
        return parse_yaml({'zabbix': {'server': 'server', 'hostname': 'host'},
                           'ping': [{'address': '1.1.1.1', 'source_ip': source, 'namespace': 'ns1', 'name': 'dns'}]})

    def test_configuration_and_summary(self):
        cfg = self.config('192.0.2.10')
        self.assertEqual(cfg.probes[0].source_ip, '192.0.2.10')
        self.assertIn('192.0.2.10', describe_config(cfg))

    def test_invalid_source_addresses(self):
        for value in ('eth0', '192.0.2.999', '::1', '-x', '', None, 123):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.config(value)

    def test_command_with_and_without_namespace(self):
        for namespace in (None, 'ns1'):
            with patch('agent.collectors.icmp.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='100% packet loss', stderr='')) as run:
                self.assertEqual(ping('1.1.1.1', 2, namespace=namespace, source_ip='192.0.2.10'), (100.0, 0.0))
                command = run.call_args.args[0]
                self.assertEqual(command[command.index('-I') + 1], '192.0.2.10')
                if namespace:
                    self.assertEqual(command[:4], ['ip', 'netns', 'exec', 'ns1'])

    def test_collector_receives_source(self):
        target = self.config('192.0.2.10').probes[0]
        with patch('agent.app.ping', return_value=(0.0, 2.0)) as collect:
            metrics = probe_metrics('host', target)
        self.assertEqual(collect.call_args.kwargs['source_ip'], '192.0.2.10')
        self.assertEqual(metrics[0].key, 'ping_get[dns,loss]')

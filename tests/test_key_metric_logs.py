import io
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent.app import probe_metrics, run_cycle
from agent.config import Config
from agent.models import Metric, Target
from agent.sender import Sender
from agent.readable_logs import ReadableFilter, ReadableFormatter
from agent.collectors.icmp import ping
from agent.collectors.tcp import tcping, parse_tcping
from agent.collectors.network import get_ns_net_io_counters
import json


class KeyMetricLogTests(unittest.TestCase):
    def test_large_error_output_is_not_reintroduced_via_exception(self):
        stderr = 'reason ' + 'x' * 2000 + 'RAW_OUTPUT_TAIL'
        for module, call, stdout in (
                ('icmp', lambda: ping('1.1.1.1', 1), ''),
                ('tcp', lambda: tcping('example.com', 443, count=1), '{"type":"error","message":"DNS failed"}'),
                ('network', lambda: get_ns_net_io_counters('ns1', 'eth0'), '')):
            with self.subTest(module=module), patch('agent.collectors.{}.subprocess.run'.format(module), return_value=SimpleNamespace(returncode=2, stdout=stdout, stderr=stderr)):
                with self.assertRaises(ValueError) as caught:
                    call()
                self.assertNotIn('RAW_OUTPUT_TAIL', str(caught.exception))
                self.assertLess(len(str(caught.exception)), 650)
        with self.assertRaises(ValueError) as caught:
            parse_tcping(json.dumps({'type': 'unknown', 'message': stderr, 'details': 'UNNEEDED_RAW_PAYLOAD'}))
        self.assertNotIn('RAW_OUTPUT_TAIL', str(caught.exception))
        self.assertNotIn('UNNEEDED_RAW_PAYLOAD', str(caught.exception))

    def test_collection_failure_has_command_and_no_fabricated_value(self):
        cfg = Config('server', 10051, 'host', False, [], [Target('icmp', '1.1.1.1', 'dns')])
        sender = SimpleNamespace(send=lambda metrics: SimpleNamespace(ok=True, processed=len(metrics), failed=0))
        with self.assertLogs('agent', level='DEBUG') as logs, patch('agent.app.ping', side_effect=ValueError('permission denied')):
            self.assertEqual(run_cycle(cfg, logging.getLogger('agent'), sender), 1)
        error = next(record for record in logs.records if getattr(record, 'event', None) == 'collection_failed')
        self.assertIn('ping -w 50', error.fields['command'])
        text = ReadableFormatter('run').format(error)
        self.assertIn('上报状态=未发送', text)
        self.assertIn('采集值=未取得', text)

    def test_probe_metric_contains_exact_source_command(self):
        target = Target('icmp', '8.8.8.8', 'dns', namespace='ns1', duration=2, source_ip='192.0.2.10')
        with patch('agent.app.ping', return_value=(0, 45.152)):
            metrics = probe_metrics('host', target)
        self.assertIn('ip netns exec ns1 ping', metrics[0].command)
        self.assertIn('-I 192.0.2.10', metrics[0].command)
        self.assertIn('8.8.8.8', metrics[0].command)

    def test_delivery_has_command_value_and_send_time(self):
        metric = Metric('host', 'delay', 45.152, 123, command='ping -q 8.8.8.8')
        sender = Sender('server', 10051,
                        transport=SimpleNamespace(send=lambda metrics: SimpleNamespace(processed=1, failed=0, total=1)),
                        metric_factory=lambda *args: args)
        with self.assertLogs('agent', level='DEBUG') as logs, patch('agent.sender.time', side_effect=[200.125, 200.25]):
            self.assertTrue(sender.send([metric]).ok)
        delivery = next(record for record in logs.records if getattr(record, 'event', None) == 'metric_delivery')
        self.assertEqual(delivery.fields['sent_at'], 200.125)
        self.assertEqual(delivery.fields['acknowledged_at'], 200.25)
        self.assertEqual(delivery.fields['command'], 'ping -q 8.8.8.8')
        self.assertEqual(delivery.fields['wire_value'], '45.15')
        text = ReadableFormatter('run').format(delivery)
        for field in ('执行命令=ping -q 8.8.8.8', '采集值=45.15', '上报值=45.15', '上报时间=', '上报成功'):
            self.assertIn(field, text)

    def test_full_probe_stdout_is_not_logged(self):
        stdout = 'PING header\n200 packets transmitted\n0% packet loss\nrtt min/avg/max/mdev = 1/2/3/4\n'
        with self.assertLogs('agent', level='DEBUG') as logs, patch('agent.collectors.icmp.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=stdout, stderr='')):
            self.assertEqual(ping('1.1.1.1', 2), (0, 2))
        result = next(record for record in logs.records if getattr(record, 'event', None) == 'command_result')
        self.assertNotIn('stdout', result.fields)
        self.assertNotIn('stderr', result.fields)
        self.assertFalse(ReadableFilter().filter(result))

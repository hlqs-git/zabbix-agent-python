import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from agent.collectors.icmp import parse_ping, ping
from agent.collectors.tcp import parse_tcping
from agent.config import load_config
from agent.discovery import build_discovery
from agent.models import Metric
from agent.sender import Sender
from agent.runtime import collect_tasks
from agent.app import run_cycle, probe_metrics
from agent.collectors.network import get_ns_net_io_counters
from agent.models import Target
import logging
import subprocess
import threading
import time
import sys
from agent.runtime import process_lock

ROOT = Path(__file__).resolve().parents[1]


class ProbeTests(unittest.TestCase):
    def test_average_and_fractional_loss(self):
        self.assertEqual(parse_ping('0.5% packet loss\nrtt min/avg/max/mdev = 1.0/2.0/3.0/4.0 ms'), (0.5, 2.0))

    def test_full_loss(self):
        self.assertEqual(parse_ping('100% packet loss'), (100.0, 0.0))

    def test_invalid_ping_is_not_packet_loss(self):
        with self.assertRaises(ValueError):
            parse_ping('')

    def test_tcp_errors(self):
        for output in ('', 'bad json', '{}', '[]', '{"type":"error","message":"DNS error"}'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                parse_tcping(output)

    def test_tcp_numeric_full_loss(self):
        self.assertEqual(parse_tcping(json.dumps({'type': 'statistics', 'addr': '1.1.1.1', 'total_packet_loss': 100})), ('1.1.1.1', 100.0, 0.0))

    def test_ping_command_is_bounded_and_english(self):
        with patch('agent.collectors.icmp.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='100% packet loss', stderr='')) as run:
            self.assertEqual(ping('1.1.1.1', 2), (100.0, 0.0))
            self.assertEqual(run.call_args.kwargs['timeout'], 7)
            self.assertEqual(run.call_args.kwargs['env']['LC_ALL'], 'C')


class ConfigTests(unittest.TestCase):
    def test_empty_discovery_clears_previous_targets(self):
        config = load_config(ROOT / 'conf/config.legacy.example.ini')
        config.interfaces = []
        config.probes = []
        metrics = build_discovery(config)
        self.assertEqual(len(metrics), 2)
        self.assertTrue(all(json.loads(metric.value) == {'data': []} for metric in metrics))

    def test_existing_config_and_complete_discovery(self):
        config = load_config(ROOT / 'conf/config.legacy.example.ini')
        self.assertEqual(len(config.probes), 4)
        metrics = build_discovery(config)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(len(json.loads(metrics[1].value)['data']), 4)

    def test_invalid_config(self):
        original = (ROOT / 'conf/config.legacy.example.ini').read_text(encoding='utf-8')
        for content in (original.replace('ServerPort=10051', 'ServerPort=70000'), original.replace('1.1.1.1,8.8.8.8', '1.1.1.1,1.1.1.1'), original.replace('ping_time = 50', 'ping_time = 0')):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'config.ini'
                path.write_text(content, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_config(path)


class SenderTests(unittest.TestCase):
    def test_batch_preserves_all_values(self):
        batches = []
        def accept(metrics):
            batches.append(metrics)
            return SimpleNamespace(processed=len(metrics), failed=0, total=len(metrics))
        sender = Sender('server', 10051, transport=SimpleNamespace(send=accept), metric_factory=lambda *args: args)
        self.assertTrue(sender.send([Metric('h', 'a', 0.5, 123), Metric('h', 'b', 2, 124)]).ok)
        self.assertEqual(batches, [[('h', 'a', '0.50', 123), ('h', 'b', 2, 124)]])

    def test_concurrency_limit(self):
        active = peak = 0
        lock = threading.Lock()
        def task():
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.01)
            with lock:
                active -= 1
            return []
        self.assertEqual(len(list(collect_tasks([(str(i), task) for i in range(8)], 2))), 8)
        self.assertLessEqual(peak, 2)

    def test_batch_and_partial_failure(self):
        transport = SimpleNamespace(send=lambda metrics: SimpleNamespace(processed=1, failed=1, total=2))
        sender = Sender('server', 10051, transport=transport, metric_factory=lambda *args: args)
        result = sender.send([Metric('host', 'a', 1, 10), Metric('host', 'b', 2, 10)])
        self.assertFalse(result.ok)
        self.assertEqual(result.processed, 1)

    def test_empty_batch(self):
        self.assertTrue(Sender('server', 10051).send([]).ok)

    def test_network_failure(self):
        def fail(metrics):
            raise OSError('offline')
        result = Sender('server', 10051, transport=SimpleNamespace(send=fail), metric_factory=lambda *args: args).send([Metric('host', 'a', 1, 10)])
        self.assertFalse(result.ok)
        self.assertIn('offline', result.error)

    def test_task_failure_isolated(self):
        def fail():
            raise ValueError('bad target')
        results = list(collect_tasks([('bad', fail), ('good', lambda: [Metric('host', 'a', 1, 10)])], 2))
        self.assertEqual(sum(len(result.metrics) for result in results), 1)
        self.assertEqual(sum(len(result.errors) for result in results), 1)


class IntegrationTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux flock')
    def test_lock_contention_and_release_after_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'agent.lock'
            with self.assertRaises(RuntimeError):
                with process_lock(path) as first:
                    self.assertTrue(first)
                    with process_lock(path) as second:
                        self.assertFalse(second)
                    raise RuntimeError('simulated cycle failure')
            with process_lock(path) as acquired:
                self.assertTrue(acquired)

    def test_fast_metrics_are_sent_in_one_batch(self):
        config = load_config(ROOT / 'conf/config.legacy.example.ini')
        config.system = False
        config.probes = []
        config.interfaces = [Target('network', 'a', 'a'), Target('network', 'b', 'b')]
        batches = []
        def accept(metrics):
            batches.append(metrics)
            return SimpleNamespace(ok=True, processed=len(metrics), failed=0)
        with patch('agent.app.network_snapshot', return_value=({}, {})), patch('agent.app.get_net_io_counters', return_value=(1, 2, 1)):
            self.assertEqual(run_cycle(config, logging.getLogger('test'), SimpleNamespace(send=accept)), 0)
        self.assertEqual([len(batch) for batch in batches], [2, 6, 0])

    def test_fractional_loss_preserved_in_metrics(self):
        with patch('agent.app.ping', return_value=(0.5, 2.0)):
            metrics = probe_metrics('host', Target('icmp', '1.1.1.1', 'dns'))
        self.assertEqual(metrics[0].key, 'ping_get[dns,loss]')
        self.assertEqual(metrics[0].value, 0.5)

    def test_cycle_reports_collection_failure_and_keeps_other_targets(self):
        config = load_config(ROOT / 'conf/config.legacy.example.ini')
        config.system = False
        config.interfaces = []
        batches = []
        def accept(metrics):
            batches.append(metrics)
            return SimpleNamespace(ok=True, processed=len(metrics), failed=0)
        with patch('agent.app.ping', side_effect=[ValueError('bad target'), (0.5, 2)]), patch('agent.app.tcping', return_value=('1.1.1.1', 0, 1)):
            status = run_cycle(config, logging.getLogger('test'), SimpleNamespace(send=accept))
        self.assertEqual(status, 1)
        discovery = next(metric for metric in batches[0] if metric.key == 'Zabbix.ping.dst_ip')
        self.assertEqual(len(json.loads(discovery.value)['data']), 4)
        self.assertEqual(sum(len(batch) for batch in batches[1:]), 6)

    def test_namespace_uses_json_and_no_shell(self):
        payload = [{'flags': ['UP', 'LOWER_UP'], 'stats64': {'rx': {'bytes': 123}, 'tx': {'bytes': 456}}}]
        with patch('agent.collectors.network.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))) as run:
            self.assertEqual(get_ns_net_io_counters('ns1', 'eth0'), (123, 456, 1))
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertEqual(run.call_args.kwargs['timeout'], 5)

    def test_probe_timeout_propagates_to_task_error(self):
        with patch('agent.collectors.icmp.subprocess.run', side_effect=subprocess.TimeoutExpired('ping', 7)):
            results = list(collect_tasks([('dns', lambda: probe_metrics('host', Target('icmp', '1.1.1.1', 'dns')))], 1))
        self.assertFalse(results[0].metrics)
        self.assertIn('TimeoutExpired', results[0].errors[0])


if __name__ == '__main__':
    unittest.main()

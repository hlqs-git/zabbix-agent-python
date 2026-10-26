import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from agent.config import Config
from agent.discovery import DiscoveryState, build_discovery
from agent.app import run_cycle
from agent.models import Target


def config(host='host', server='server'):
    return Config(server, 10051, host, False, [Target('network', 'eth0', 'wan')], [])


class DiscoveryStateTests(unittest.TestCase):
    def test_invalid_cached_timestamps_trigger_resend(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            cfg = config()
            metrics = build_discovery(cfg)
            for value in (True, 'bad time', -1, 10 ** 1000, float('inf'), float('nan')):
                state = DiscoveryState(path)
                state.acknowledge(metrics, cfg.server, cfg.port, now=100)
                data = json.loads(path.read_text(encoding='utf-8'))
                for entry in data['entries'].values():
                    entry['sent_at'] = value
                path.write_text(json.dumps(data), encoding='utf-8')
                self.assertEqual(len(DiscoveryState(path).pending(metrics, cfg.server, cfg.port, now=101)), 2)

    def test_regular_metrics_continue_when_discovery_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            cfg = config()
            cfg.interfaces = []
            cfg.probes = [Target('icmp', '1.1.1.1', 'dns')]
            batches = []
            def send(metrics):
                if metrics:
                    batches.append(metrics)
                return SimpleNamespace(ok=True, processed=len(metrics), failed=0)
            with patch('agent.app.ping', return_value=(0, 1)):
                for _ in range(2):
                    self.assertEqual(run_cycle(cfg, logging.getLogger('test'), SimpleNamespace(send=send), discovery_state_path=path), 0)
            self.assertEqual(len(batches), 3)
            self.assertTrue(all(metric.key.startswith('ping_get[') for batch in batches[1:] for metric in batch))

    def test_failed_cache_write_still_sends_regular_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            cfg = config()
            cfg.interfaces = []
            cfg.probes = [Target('icmp', '1.1.1.1', 'dns')]
            keys = []
            def send(metrics):
                keys.extend(metric.key for metric in metrics)
                return SimpleNamespace(ok=True, processed=len(metrics), failed=0)
            with patch('agent.app.ping', return_value=(0, 1)), patch('agent.discovery.os.replace', side_effect=OSError('disk error')):
                self.assertEqual(run_cycle(cfg, logging.getLogger('test'), SimpleNamespace(send=send), discovery_state_path=path), 1)
            self.assertIn('ping_get[dns,loss]', keys)
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_first_unchanged_heartbeat_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            cfg = config()
            metrics = build_discovery(cfg)
            state = DiscoveryState(path)
            self.assertEqual(len(state.pending(metrics, cfg.server, cfg.port, now=100)), 2)
            state.acknowledge(metrics, cfg.server, cfg.port, now=100)
            restarted = DiscoveryState(path)
            self.assertEqual(restarted.pending(metrics, cfg.server, cfg.port, now=3699), [])
            self.assertEqual(len(restarted.pending(metrics, cfg.server, cfg.port, now=3700)), 2)

    def test_change_empty_and_destination_identity(self):
        state = DiscoveryState()
        cfg = config()
        state.acknowledge(build_discovery(cfg), cfg.server, cfg.port, now=100)
        cfg.interfaces = []
        changed = state.pending(build_discovery(cfg), cfg.server, cfg.port, now=101)
        self.assertEqual([metric.key for metric in changed], ['Zabbix.interface'])
        self.assertEqual(json.loads(changed[0].value), {'data': []})
        for changed_cfg, port in ((config(server='new-server'), 10051), (config(host='new-host'), 10051), (config(), 10052)):
            self.assertEqual(len(state.pending(build_discovery(changed_cfg), changed_cfg.server, port, now=101)), 2)

    def test_reordering_does_not_trigger_discovery(self):
        cfg = config()
        cfg.interfaces.append(Target('network', 'eth1', 'lan'))
        state = DiscoveryState()
        state.acknowledge(build_discovery(cfg), cfg.server, cfg.port, now=100)
        cfg.interfaces.reverse()
        self.assertEqual(state.pending(build_discovery(cfg), cfg.server, cfg.port, now=101), [])

    def test_corrupt_cache_and_clock_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('broken json', encoding='utf-8')
            cfg = config()
            state = DiscoveryState(path)
            metrics = build_discovery(cfg)
            self.assertEqual(len(state.pending(metrics, cfg.server, cfg.port, now=100)), 2)
            state.acknowledge(metrics, cfg.server, cfg.port, now=100)
            self.assertEqual(len(state.pending(metrics, cfg.server, cfg.port, now=99)), 2)

    def test_failed_or_partial_send_does_not_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            cfg = config()
            cfg.interfaces = []
            responses = [SimpleNamespace(ok=False, processed=1, failed=1, error='partial'), SimpleNamespace(ok=True, processed=2, failed=0, error='')]
            batches = []
            def send(metrics):
                if not metrics:
                    return SimpleNamespace(ok=True, processed=0, failed=0)
                batches.append(metrics)
                return responses.pop(0)
            sender = SimpleNamespace(send=send)
            self.assertEqual(run_cycle(cfg, logging.getLogger('test'), sender, discovery_state_path=path), 1)
            self.assertFalse(path.exists())
            self.assertEqual(run_cycle(cfg, logging.getLogger('test'), sender, discovery_state_path=path), 0)
            self.assertEqual(len(batches), 2)
            self.assertTrue(path.exists())
            self.assertEqual(run_cycle(cfg, logging.getLogger('test'), sender, discovery_state_path=path), 0)
            self.assertEqual(len(batches), 2)

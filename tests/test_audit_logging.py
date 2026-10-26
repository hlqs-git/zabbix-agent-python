import io
import json
import logging
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent.logging_setup import setup_logging
from agent.models import Metric
from agent.sender import Sender
from agent.yaml_config import parse_yaml
from agent.collectors.icmp import ping
from datetime import datetime, timedelta
from contextlib import redirect_stdout
from agent.app import main
from agent.app import run_cycle


class AuditLoggingTests(unittest.TestCase):
    def test_retention_keeps_nonstandard_backup_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ['agent.log.' + (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d') for days in (30, 1, 0)]
            backup = root / (names[0] + '.backup')
            backup.write_text('manual archive', encoding='utf-8')
            for name in names[1:]:
                (root / name).write_text('recent', encoding='utf-8')
            logger = setup_logging(root, console=False, retention_days=1)
            try:
                self.assertTrue(backup.exists())
                self.assertTrue(all((root / name).exists() for name in names[1:]))
            finally:
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
                    handler.close()

    def test_complete_cycle_links_values_to_delivery_records(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = setup_logging(Path(directory), level='DEBUG', console=False, run_id='audit-cycle')
            cfg = parse_yaml({'zabbix': {'server': 'server', 'hostname': 'host'}, 'ping': [{'address': '1.1.1.1'}]})
            def accept(metrics):
                self.assertEqual(len(metrics), 1)
                return SimpleNamespace(processed=1, failed=0, total=1)
            sender = Sender('server', 10051, transport=SimpleNamespace(send=accept), metric_factory=lambda *args: args)
            try:
                with patch('agent.app.ping', return_value=(0.5, 2.25)):
                    self.assertEqual(run_cycle(cfg, logger, sender), 0)
                records = [json.loads(line) for line in (Path(directory) / 'audit.jsonl').read_text(encoding='utf-8').splitlines()]
                collected = [record['fields'] for record in records if record['event'] == 'metric_collected']
                delivered = [record['fields'] for record in records if record['event'] == 'metric_delivery']
                self.assertEqual(len(collected), 4)
                self.assertEqual({item['metric_id'] for item in collected}, {item['metric_id'] for item in delivered})
                loss = next(item for item in delivered if item['key'] == 'ping_get[1.1.1.1,loss]')
                self.assertEqual((loss['value'], loss['status']), (0.5, 'accepted'))
                self.assertTrue(all(record['run_id'] == 'audit-cycle' for record in records))
            finally:
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
                    handler.close()

    def test_incomplete_response_is_unconfirmed(self):
        transport = SimpleNamespace(send=lambda metrics: SimpleNamespace(processed=0, failed=0, total=0))
        with self.assertLogs('agent', level='DEBUG') as logs:
            result = Sender('server', 10051, transport=transport, metric_factory=lambda *args: args).send([Metric('h', 'a', 1, 123)])
        outcome = next(record.fields for record in logs.records if getattr(record, 'event', None) == 'metric_delivery')
        self.assertEqual(outcome['status'], 'unconfirmed')
        self.assertEqual(result.unconfirmed, 1)

    def test_retention_removes_expired_calendar_days(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / ('agent.log.' + (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'))
            recent = root / ('agent.log.' + (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
            old.write_text('old', encoding='utf-8')
            recent.write_text('recent', encoding='utf-8')
            logger = setup_logging(root, console=False, retention_days=7)
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                handler.close()

    def test_cli_override_works_without_creating_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'
            path.write_text('zabbix:\n  server: server\n  hostname: host\n', encoding='utf-8')
            output = io.StringIO()
            with redirect_stdout(output), patch('agent.app.setup_logging') as setup:
                self.assertEqual(main(['--config', str(path), '--check-config', '--log-level', 'debug']), 0)
            self.assertIn('DEBUG', output.getvalue())
            setup.assert_not_called()

    def test_payload_construction_failure_is_not_sent(self):
        def fail(*args):
            raise ValueError('cannot encode')
        transport = SimpleNamespace(send=lambda metrics: self.fail('must not send'))
        with self.assertLogs('agent', level='DEBUG') as logs:
            result = Sender('server', 10051, transport=transport, metric_factory=fail).send([Metric('host', 'a', 1, 123)])
        outcome = next(record.fields for record in logs.records if getattr(record, 'event', None) == 'metric_delivery')
        self.assertEqual(outcome['status'], 'not_sent')
        self.assertEqual(result.unconfirmed, 0)

    def setUp(self):
        self.logger = logging.getLogger('agent')
        self.old_level = self.logger.level
        self.old_propagate = self.logger.propagate

    def tearDown(self):
        for handler in self.logger.handlers[:]:
            if getattr(handler, '_agent_owned', False):
                self.logger.removeHandler(handler)
                handler.close()
        self.logger.setLevel(self.old_level)
        self.logger.propagate = self.old_propagate

    def test_configuration_and_invalid_values(self):
        base = {'zabbix': {'server': 'server', 'hostname': 'host'}}
        cfg = parse_yaml(dict(base, logging={'level': 'debug', 'console': False, 'retention_days': 7}))
        self.assertEqual((cfg.log_level, cfg.log_console, cfg.log_retention_days), ('DEBUG', False, 7))
        for value in ({'level': 'verbose'}, {'console': 'false'}, {'retention_days': 0}, {'levels': 'DEBUG'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_yaml(dict(base, logging=value))

    def test_json_records_and_reinitialization(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = setup_logging(Path(directory), level='DEBUG', console=False, retention_days=7, run_id='run-one')
            logger.debug('raw line\nnext line', extra={'event': 'raw', 'fields': {'value': 0.5}})
            setup_logging(Path(directory), level='INFO', console=False, retention_days=7, run_id='run-two')
            logger.debug('must be filtered')
            logger.info('second event')
            for handler in logger.handlers:
                handler.flush()
            records = [json.loads(line) for line in (Path(directory) / 'audit.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]['run_id'], 'run-one')
            self.assertEqual(records[0]['fields']['value'], 0.5)
            self.assertEqual(records[1]['run_id'], 'run-two')
            self.assertIn('pid', records[0])
            self.assertIn('thread', records[0])
            self.assertEqual(logger.handlers[0].backupCount, 7)
            # Close the file before Windows TemporaryDirectory cleanup.
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                handler.close()

    def test_debug_per_metric_acknowledgements(self):
        requests = []
        def send(metrics):
            requests.append(metrics)
            if metrics[0][1] == 'bad':
                return SimpleNamespace(processed=0, failed=1, total=1)
            return SimpleNamespace(processed=1, failed=0, total=1)
        sender = Sender('server', 10051, transport=SimpleNamespace(send=send), metric_factory=lambda *args: args)
        with self.assertLogs('agent', level='DEBUG') as logs:
            result = sender.send([Metric('host', 'good', 0.5, 123), Metric('host', 'bad', 7, 123)])
        self.assertEqual([len(request) for request in requests], [1, 1])
        self.assertEqual((result.processed, result.failed), (1, 1))
        outcomes = [record.fields for record in logs.records if getattr(record, 'event', None) == 'metric_delivery']
        self.assertEqual([(item['key'], item['status']) for item in outcomes], [('good', 'accepted'), ('bad', 'rejected')])
        self.assertEqual(outcomes[0]['value'], 0.5)
        self.assertEqual(outcomes[0]['clock'], 123)

    def test_network_failure_is_unconfirmed_and_next_metric_continues(self):
        calls = 0
        def send(metrics):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('response lost')
            return SimpleNamespace(processed=1, failed=0, total=1)
        sender = Sender('server', 10051, transport=SimpleNamespace(send=send), metric_factory=lambda *args: args)
        with self.assertLogs('agent', level='DEBUG') as logs:
            result = sender.send([Metric('host', 'first', 1, 123), Metric('host', 'second', 2, 123)])
        statuses = [record.fields['status'] for record in logs.records if getattr(record, 'event', None) == 'metric_delivery']
        self.assertEqual(statuses, ['unconfirmed', 'accepted'])
        self.assertEqual(result.unconfirmed, 1)

    def test_raw_ping_output_logged(self):
        output = '100% packet loss\n'
        with self.assertLogs('agent', level='DEBUG') as logs, patch('agent.collectors.icmp.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout=output, stderr='')):
            ping('1.1.1.1', 1)
        records = [record for record in logs.records if getattr(record, 'event', None) == 'command_result']
        self.assertEqual(records[0].fields['stdout'], output)
        self.assertEqual(records[0].fields['returncode'], 1)

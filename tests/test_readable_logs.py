import io
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent.logging_setup import setup_logging
from agent.audit import event


class ReadableLoggingTests(unittest.TestCase):
    def test_each_event_is_exactly_one_line(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = setup_logging(Path(directory), level='DEBUG', console=False)
            events = [
                ('agent_start', {'log_level': 'DEBUG', 'retention_days': 14}),
                ('metric_delivery', {'key': 'ping_get[dns,delay]', 'value': 45.152, 'wire_value': '45.15',
                    'clock': 1792996133, 'sent_at': 1792996133.218, 'status': 'accepted',
                    'command': 'ping -q 8.8.8.8', 'error': ''}),
                ('collection_failed', {'target': 'dns', 'command': 'ping 8.8.8.8', 'error': 'line one\nline two\rline three\u2028line four'}),
                ('command_error', {'command': ['ping', '8.8.8.8'], 'error': 'failed\nreason', 'error_summary': 'summary'})]
            for name, fields in events:
                event(logger, logging.DEBUG, name, **fields)
            self.close()
            lines = (Path(directory) / 'agent.log').read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines), len(events))
            delivery = next(line for line in lines if 'ping_get[dns,delay]' in line)
            for value in ('上报成功', '采集值=45.15', '上报值=45.15', '执行命令=ping -q 8.8.8.8', '上报时间='):
                self.assertIn(value, delivery)
            self.assertTrue(all(line[:4].isdigit() for line in lines))
            audit = [json.loads(line) for line in (Path(directory) / 'audit.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(audit), len(events))
            self.assertEqual(audit[2]['fields']['error'], events[2][1]['error'])

    def test_exception_stack_stays_in_audit_with_concise_readable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = setup_logging(Path(directory), level='DEBUG', console=False)
            try:
                try:
                    raise ValueError('DNS lookup timed out')
                except ValueError:
                    logging.getLogger('agent.runtime').debug('Collection task failed: example.com:443', exc_info=True)
                event(logger, logging.ERROR, 'collection_failed', error='example.com:443: DNS lookup timed out')
            finally:
                self.close()
            readable = (Path(directory) / 'agent.log').read_text(encoding='utf-8')
            self.assertIn('采集失败', readable)
            self.assertEqual(readable.count('DNS lookup timed out'), 1)
            self.assertNotIn('Traceback', readable)
            audit = [json.loads(line) for line in (Path(directory) / 'audit.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(audit), 2)
            self.assertIn('Traceback', audit[0]['exception'])
            self.assertIn('DNS lookup timed out', audit[0]['exception'])

    def setUp(self):
        self.logger = logging.getLogger('agent')
        self.old_level, self.old_propagate = self.logger.level, self.logger.propagate

    def tearDown(self):
        self.close()
        self.logger.setLevel(self.old_level)
        self.logger.propagate = self.old_propagate

    def close(self):
        for handler in self.logger.handlers[:]:
            if getattr(handler, '_agent_owned', False):
                self.logger.removeHandler(handler)
                handler.close()

    def test_one_readable_result_and_complete_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            console = io.StringIO()
            with patch('sys.stderr', console):
                logger = setup_logging(Path(directory), level='DEBUG', run_id='readable-run')
                fields = dict(host='host', key='ping_get[dns,delay]', value=45.668, clock=123, metric_id='metric-one')
                event(logger, logging.DEBUG, 'metric_collected', **fields)
                event(logger, logging.DEBUG, 'metric_send', **fields, wire_value='45.67')
                event(logger, logging.DEBUG, 'zabbix_response', response='processed:1')
                event(logger, logging.DEBUG, 'metric_delivery', **fields, wire_value='45.67', status='accepted', elapsed_ms=21.2, response={'processed': 1, 'failed': 0, 'total': 1}, error='')
            self.close()
            readable = (Path(directory) / 'agent.log').read_text(encoding='utf-8')
            self.assertIn('上报成功', readable)
            self.assertIn('采集值=45.67', readable)
            self.assertIn('上报值=45.67', readable)
            self.assertEqual(readable.count('ping_get[dns,delay]'), 1)
            self.assertNotIn('"fields"', console.getvalue())
            self.assertEqual(console.getvalue(), readable)
            records = [json.loads(line) for line in (Path(directory) / 'audit.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([record['event'] for record in records], ['metric_collected', 'metric_delivery'])
            self.assertNotIn('message', records[1])
            self.assertNotIn('error', records[1]['fields'])
            self.assertTrue(all(record['run_id'] == 'readable-run' for record in records))

    def test_command_events_do_not_clutter_readable_log(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = setup_logging(Path(directory), level='DEBUG', console=False)
            stdout = 'PING 1.1.1.1\n0% packet loss\nrtt min/avg/max/mdev = 1/2/3/4\n'
            event(logger, logging.DEBUG, 'command_result', command=['ping', '1.1.1.1'], stdout=stdout, stderr='', returncode=0, elapsed_ms=1000)
            self.close()
            readable = (Path(directory) / 'agent.log').read_text(encoding='utf-8')
            self.assertEqual(readable, '')
            record = json.loads((Path(directory) / 'audit.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(record['fields']['stdout'], stdout)

    def test_error_statuses_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            logger = setup_logging(Path(directory), level='DEBUG', console=False)
            for status in ('rejected', 'unconfirmed', 'not_sent'):
                event(logger, logging.DEBUG, 'metric_delivery', key=status, value=1, clock=123, status=status, error='test reason')
            self.close()
            readable = (Path(directory) / 'agent.log').read_text(encoding='utf-8')
            for text in ('服务端拒收', '上报未确认', '尚未发送', 'test reason'):
                self.assertIn(text, readable)

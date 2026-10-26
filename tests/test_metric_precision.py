import logging
from types import SimpleNamespace
import unittest

from agent.models import Metric
from agent.sender import Sender


class MetricPrecisionTests(unittest.TestCase):
    def test_two_decimal_wire_values_in_batch_and_debug(self):
        logger = logging.getLogger('agent.sender')
        old_level = logger.level
        values = [45.668, 5.6, 0.0, 1.005, -1.235, -0.004, 1234567890123456789, 1, '{"data": []}']
        expected = ['45.67', '5.60', '0.00', '1.01', '-1.24', '0.00', 1234567890123456789, 1, '{"data": []}']
        try:
            for level in (logging.INFO, logging.DEBUG):
                logger.setLevel(level)
                captured = []
                def send(metrics):
                    captured.extend(metrics)
                    return SimpleNamespace(processed=len(metrics), failed=0, total=len(metrics))
                sender = Sender('server', 10051, transport=SimpleNamespace(send=send),
                                metric_factory=lambda h, k, v, t: SimpleNamespace(host=h, key=k, value=v, clock=t))
                metrics = [Metric('host', 'key{}'.format(i), value, 123) for i, value in enumerate(values)]
                self.assertTrue(sender.send(metrics).ok)
                self.assertEqual([item.value for item in captured], expected)
                self.assertEqual([metric.value for metric in metrics], values)
        finally:
            logger.setLevel(old_level)

    def test_audit_keeps_original_and_records_rounded_wire_value(self):
        sender = Sender('server', 10051,
                        transport=SimpleNamespace(send=lambda metrics: SimpleNamespace(processed=1, failed=0, total=1)),
                        metric_factory=lambda *args: args)
        with self.assertLogs('agent', level='DEBUG') as logs:
            self.assertTrue(sender.send([Metric('host', 'delay', 45.668, 123)]).ok)
        outcome = next(record.fields for record in logs.records if getattr(record, 'event', None) == 'metric_delivery')
        self.assertEqual(outcome['value'], 45.668)
        self.assertEqual(outcome['wire_value'], '45.67')

from dataclasses import dataclass
import logging
from time import monotonic
from .audit import event, metric_fields
from .precision import metric_value

logger = logging.getLogger('agent.sender')


@dataclass
class SendResult:
    processed: int
    failed: int
    error: str = ''
    unconfirmed: int = 0

    @property
    def ok(self):
        return self.failed == 0 and not self.error


class Sender:
    def __init__(self, server, port, timeout=5, transport=None, metric_factory=None):
        self.server, self.port, self.timeout = server, port, timeout
        self.transport, self.metric_factory = transport, metric_factory

    def send(self, metrics):
        if not metrics:
            return SendResult(0, 0)
        if logger.isEnabledFor(logging.DEBUG):
            results = [self._send_batch([metric]) for metric in metrics]
            return SendResult(sum(result.processed for result in results),
                              sum(result.failed for result in results),
                              '; '.join(result.error for result in results if result.error),
                              sum(result.unconfirmed for result in results))
        return self._send_batch(metrics)

    def _send_batch(self, metrics):
        started = monotonic()
        status = 'not_sent'
        response_data = None
        error = ''
        wire_values = [None] * len(metrics)
        try:
            if self.transport is None:
                from pyzabbix import ZabbixMetric, ZabbixSender
                self.transport = ZabbixSender(zabbix_server=self.server, zabbix_port=self.port, timeout=self.timeout)
                self.metric_factory = ZabbixMetric
            values = [metric_value(metric.value) for metric in metrics]
            data = [self.metric_factory(metric.host, metric.key, value, metric.timestamp) for metric, value in zip(metrics, values)]
            wire_values = [getattr(wire, 'value', str(value)) for value, wire in zip(values, data)]
            for metric, wire_value in zip(metrics, wire_values):
                event(logger, logging.DEBUG, 'metric_send', **metric_fields(metric),
                      server=self.server, port=self.port, wire_value=wire_value)
            status = 'unconfirmed'
            response = self.transport.send(data)
            event(logger, logging.DEBUG, 'zabbix_response', server=self.server, port=self.port,
                  metric_ids=[metric_fields(metric)['metric_id'] for metric in metrics], response=repr(response))
            response_data = {'processed': response.processed, 'failed': response.failed, 'total': response.total}
            if (any(type(value) is not int or value < 0 for value in response_data.values())
                    or response.total != len(data) or response.processed + response.failed != len(data)):
                error = 'Incomplete or invalid Zabbix response'
                result = SendResult(0, len(data), error, len(data))
            else:
                status = 'accepted' if response.failed == 0 else ('rejected' if response.processed == 0 else 'unconfirmed')
                result = SendResult(response.processed, response.failed)
        except Exception as exc:
            # Delivery may have occurred before the response was lost. Do not retry automatically.
            error = '{}: {}'.format(type(exc).__name__, exc)
            logger.debug('Zabbix send exception stack', exc_info=True)
            result = SendResult(0, len(metrics), error, len(metrics) if status == 'unconfirmed' else 0)
        for metric, wire_value in zip(metrics, wire_values):
            event(logger, logging.DEBUG, 'metric_delivery', **metric_fields(metric), server=self.server,
                  port=self.port, status=status, response=response_data, error=error, wire_value=wire_value,
                  elapsed_ms=round((monotonic() - started) * 1000, 3))
        return result

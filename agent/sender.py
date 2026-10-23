from dataclasses import dataclass


@dataclass
class SendResult:
    processed: int
    failed: int
    error: str = ''

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
        try:
            if self.transport is None:
                from pyzabbix import ZabbixMetric, ZabbixSender
                self.transport = ZabbixSender(zabbix_server=self.server, zabbix_port=self.port, timeout=self.timeout)
                self.metric_factory = ZabbixMetric
            data = [self.metric_factory(m.host, m.key, m.value, m.timestamp) for m in metrics]
            response = self.transport.send(data)
            if response.total != len(data) or response.processed + response.failed != len(data):
                return SendResult(response.processed, max(1, len(data) - response.processed), 'Incomplete Zabbix response')
            return SendResult(response.processed, response.failed)
        except Exception as exc:
            # Delivery may have occurred before the response was lost. Do not retry automatically.
            return SendResult(0, len(metrics), '{}: {}'.format(type(exc).__name__, exc))

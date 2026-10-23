"""Legacy single-metric sender compatibility wrapper."""
from agent.models import Metric
from agent.sender import Sender


def report_to_zabbix(server_ip, server_port, hostname, key, value, timestamp):
    result = Sender(server_ip, server_port).send([Metric(hostname, key, value, timestamp)])
    return 'OK' if result.ok else 'Error'

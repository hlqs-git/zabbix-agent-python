import json
from time import time
from .models import Metric


def build_discovery(config):
    metrics = []
    for targets, key, macro in ((config.interfaces, 'Zabbix.interface', '{#IFNAME}'),
                                (config.probes, 'Zabbix.ping.dst_ip', '{#DST_IP}')):
        payload = {'data': [{macro: target.name} for target in targets]}
        metrics.append(Metric(config.hostname, key, json.dumps(payload, ensure_ascii=False), int(time())))
    return metrics

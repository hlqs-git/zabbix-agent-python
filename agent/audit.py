"""Structured audit events shared by collectors and sender."""
import hashlib
import json


def event(logger, level, name, **fields):
    if logger.isEnabledFor(level):
        logger.log(level, name, extra={'event': name, 'fields': fields})


def metric_fields(metric):
    identity = json.dumps([metric.host, metric.key, metric.value, metric.timestamp], ensure_ascii=False, default=str)
    return {'metric_id': hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20],
            'host': metric.host, 'key': metric.key, 'value': metric.value, 'clock': metric.timestamp,
            'command': metric.command}

import json
import hashlib
import logging
import os
from pathlib import Path
import tempfile
from time import time
from .models import Metric
from .audit import event


def build_discovery(config):
    metrics = []
    for targets, key, macro in ((config.interfaces, 'Zabbix.interface', '{#IFNAME}'),
                                (config.probes, 'Zabbix.ping.dst_ip', '{#DST_IP}')):
        payload = {'data': [{macro: name} for name in sorted(target.name for target in targets)]}
        metrics.append(Metric(config.hostname, key, json.dumps(payload, ensure_ascii=False), int(time()), '配置自动发现（无外部命令）'))
    return metrics


class DiscoveryState:
    """Persist only confirmed sends. The caller owns the process lock."""

    HEARTBEAT_SECONDS = 3600

    def __init__(self, path=None, logger=None):
        self.path = Path(path) if path is not None else None
        self.logger = logger or logging.getLogger(__name__)
        self.entries = {}
        if self.path is not None:
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('entries'), dict):
                    raise ValueError('unsupported discovery cache')
                self.entries = data['entries']
            except FileNotFoundError:
                pass
            except (OSError, ValueError, UnicodeError) as exc:
                self.logger.warning('Discovery cache unavailable; sending full discovery: %s', exc)

    @staticmethod
    def _identity(metric, server, port):
        return json.dumps([server, port, metric.host, metric.key], ensure_ascii=False)

    @staticmethod
    def _fingerprint(metric):
        return hashlib.sha256(metric.value.encode('utf-8')).hexdigest()

    def pending(self, metrics, server, port, now=None):
        now = time() if now is None else now
        pending = []
        for metric in metrics:
            previous = self.entries.get(self._identity(metric, server, port))
            sent_at = previous.get('sent_at') if isinstance(previous, dict) else None
            valid_time = type(sent_at) in (int, float) and 0 <= sent_at <= now
            changed = not isinstance(previous, dict) or previous.get('fingerprint') != self._fingerprint(metric)
            due = not valid_time or changed or now - sent_at >= self.HEARTBEAT_SECONDS
            reason = 'first_or_invalid_cache' if not valid_time else ('changed' if changed else ('heartbeat' if due else 'unchanged'))
            event(self.logger, logging.INFO if due else logging.DEBUG, 'discovery_decision',
                  host=metric.host, key=metric.key, reason=reason, due=due, last_sent=sent_at, server=server, port=port)
            if due:
                pending.append(metric)
        return pending

    def acknowledge(self, metrics, server, port, now=None):
        now = time() if now is None else now
        for metric in metrics:
            self.entries[self._identity(metric, server, port)] = {'fingerprint': self._fingerprint(metric), 'sent_at': now}
        if not metrics or self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=str(self.path.parent), delete=False) as handle:
                temporary = handle.name
                json.dump({'version': 1, 'entries': self.entries}, handle, ensure_ascii=False)
            os.replace(temporary, self.path)
            temporary = None
            event(self.logger, logging.DEBUG, 'discovery_cache_saved', path=str(self.path), rules=len(metrics))
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

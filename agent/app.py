"""Run a single collection cycle; cron owns scheduling."""
import argparse
from functools import partial
import sys
from time import monotonic, time

from .config import ROOT, load_config
from .discovery import build_discovery
from .logging_setup import setup_logging
from .models import Metric
from .runtime import collect_tasks, process_lock
from .sender import Sender
from .collectors.system import get_system_load
from .collectors.network import get_net_io_counters, get_ns_net_io_counters, network_snapshot
from .collectors.icmp import ping
from .collectors.tcp import tcping


def system_metrics(host):
    values = get_system_load()
    names = [('CPU', 'cpu'), ('load_avg_1', 'load_1'), ('load_avg_5', 'load_5'),
             ('load_avg_15', 'load_15'), ('memory', 'mem_used_percent'), ('disk', 'disk_used_percent')]
    timestamp = int(time())
    return [Metric(host, 'sysload_get[{}]'.format(key), values[field], timestamp) for key, field in names]


def interface_metrics(host, target, snapshot=None):
    values = (get_ns_net_io_counters(target.namespace, target.address) if target.namespace
              else get_net_io_counters(target.address, snapshot))
    timestamp = int(time())
    return [Metric(host, 'IF_get[{},{}]'.format(target.name, field), value, timestamp)
            for field, value in zip(('In_traff', 'Out_traff', 'status'), values)]


def probe_metrics(host, target):
    if target.kind == 'icmp':
        loss, delay = ping(target.address, target.duration, namespace=target.namespace)
    else:
        _, loss, delay = tcping(target.address, target.port, target.duration, target.timeout, namespace=target.namespace)
    timestamp = int(time())
    return [Metric(host, 'ping_get[{},{}]'.format(target.name, field), value, timestamp)
            for field, value in (('loss', loss), ('delay', delay))]


def run_cycle(config, logger, sender=None):
    sender = sender or Sender(config.server, config.port, config.send_timeout)
    started = monotonic()
    processed = failed = errors = 0

    def send(metrics):
        nonlocal processed, failed
        result = sender.send(metrics)
        processed += result.processed
        failed += result.failed
        if not result.ok:
            logger.error('Zabbix send failed: processed=%s failed=%s error=%s', result.processed, result.failed, result.error)

    send(build_discovery(config))
    quick = []
    if config.system:
        quick.append(('system', partial(system_metrics, config.hostname)))
    snapshot = None
    if any(not target.namespace for target in config.interfaces):
        try:
            snapshot = network_snapshot()
        except Exception as exc:
            errors += 1
            logger.error('Network snapshot failed: %s', exc)
    for target in config.interfaces:
        quick.append((target.name, partial(interface_metrics, config.hostname, target, snapshot)))
    slow = [(target.name, partial(probe_metrics, config.hostname, target)) for target in config.probes]
    # Fast metrics are one batch; long probes cannot delay their delivery.
    for tasks in (quick, slow):
        pending = []
        for result in collect_tasks(tasks, config.workers):
            errors += len(result.errors)
            for error in result.errors:
                logger.error('Collection failed: %s', error)
            pending.extend(result.metrics)
        send(pending)
    logger.info('Cycle finished: processed=%s failed=%s collection_errors=%s elapsed=%.2fs', processed, failed, errors, monotonic() - started)
    return 1 if failed or errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Collect Linux metrics and send to Zabbix')
    parser.add_argument('--config', help='INI configuration path')
    parser.add_argument('--check-config', action='store_true', help='Validate configuration without collecting or sending')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.check_config:
        print('Configuration OK: {} interfaces, {} probes'.format(len(config.interfaces), len(config.probes)))
        return 0
    if not sys.platform.startswith('linux'):
        print('Collection requires Linux; use --check-config on other platforms.', file=sys.stderr)
        return 2
    try:
        logger = setup_logging(ROOT / 'log')
        with process_lock(ROOT / 'log/agent.lock') as acquired:
            if not acquired:
                logger.warning('Previous cycle is still running; skipping')
                return 0
            return run_cycle(config, logger)
    except Exception as exc:
        print('Agent failed: {}: {}'.format(type(exc).__name__, exc), file=sys.stderr)
        return 1

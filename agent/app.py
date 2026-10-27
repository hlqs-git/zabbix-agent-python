"""Run a single collection cycle; cron owns scheduling."""
import argparse
from functools import partial
import sys
import logging
import shlex
from dataclasses import asdict, replace
from time import monotonic, time

from .config import ROOT, load_config
from .discovery import DiscoveryState, build_discovery
from .logging_setup import LEVELS, setup_logging
from .audit import event, metric_fields
from .models import Metric
from .runtime import collect_tasks, process_lock
from .sender import Sender
from .collectors.system import get_system_load
from .collectors.network import get_net_io_counters, get_ns_net_io_counters, network_snapshot, namespace_command
from .collectors.icmp import ping, ping_command
from .collectors.tcp import tcping, tcping_command


def collect_with_context(context_command, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        exc.collection_command = context_command
        raise


def system_metrics(host):
    event(logging.getLogger('agent.collectors.system'), logging.DEBUG, 'collector_start', kind='system', host=host)
    values = collect_with_context('psutil CPU/load/memory/disk APIs', get_system_load)
    names = [('CPU', 'cpu'), ('load_avg_1', 'load_1'), ('load_avg_5', 'load_5'),
             ('load_avg_15', 'load_15'), ('memory', 'mem_used_percent'), ('disk', 'disk_used_percent')]
    timestamp = int(time())
    commands = {'cpu': 'psutil.cpu_percent(interval=1)', 'load_1': 'psutil.getloadavg()[0]',
                'load_5': 'psutil.getloadavg()[1]', 'load_15': 'psutil.getloadavg()[2]',
                'mem_used_percent': 'psutil.virtual_memory().percent', 'disk_used_percent': "psutil.disk_usage('/').percent"}
    return [Metric(host, 'sysload_get[{}]'.format(key), values[field], timestamp, commands[field]) for key, field in names]


def interface_metrics(host, target, snapshot=None):
    event(logging.getLogger('agent.collectors.network'), logging.DEBUG, 'collector_start', host=host, target=asdict(target))
    namespace_args = namespace_command(target.namespace, target.address) if target.namespace else None
    command = shlex.join(namespace_args) if target.namespace else 'psutil.net_io_counters(pernic=True); psutil.net_if_stats()'
    values = (collect_with_context(command, get_ns_net_io_counters, target.namespace, target.address, command=namespace_args) if target.namespace
              else collect_with_context(command, get_net_io_counters, target.address, snapshot))
    timestamp = int(time())
    return [Metric(host, 'IF_get[{},{}]'.format(target.name, field), value, timestamp, command)
            for field, value in zip(('In_traff', 'Out_traff', 'status'), values)]


def probe_metrics(host, target):
    event(logging.getLogger('agent.collectors.probe'), logging.DEBUG, 'collector_start', host=host, target=asdict(target))
    if target.kind == 'icmp':
        command = ping_command(target.address, target.duration, namespace=target.namespace, source_ip=target.source_ip)
        loss, delay = collect_with_context(shlex.join(command), ping, target.address, target.duration, namespace=target.namespace, source_ip=target.source_ip, command=command)
    else:
        command = tcping_command(target.address, target.port, target.duration, target.timeout, namespace=target.namespace)
        _, loss, delay = collect_with_context(shlex.join(command), tcping, target.address, target.port, target.duration, target.timeout, namespace=target.namespace, command=command)
    timestamp = int(time())
    return [Metric(host, 'ping_get[{},{}]'.format(target.name, field), value, timestamp, shlex.join(command))
            for field, value in (('loss', loss), ('delay', delay))]


def run_cycle(config, logger, sender=None, discovery_state_path=None):
    sender = sender or Sender(config.server, config.port, config.send_timeout)
    started = monotonic()
    processed = failed = errors = unconfirmed = 0
    event(logger, logging.INFO, 'cycle_start', server=config.server, port=config.port, host=config.hostname,
          system=config.system, interfaces=len(config.interfaces), probes=len(config.probes),
          workers=config.workers, send_mode='per_metric' if logging.getLogger('agent.sender').isEnabledFor(logging.DEBUG) else 'batch')

    def send(metrics):
        nonlocal processed, failed, unconfirmed
        for metric in metrics:
            event(logger, logging.DEBUG, 'metric_collected', **metric_fields(metric),
                  kind='discovery' if metric.key.startswith('Zabbix.') else 'measurement')
        result = sender.send(metrics)
        processed += result.processed
        failed += result.failed
        unconfirmed += getattr(result, 'unconfirmed', 0)
        if not result.ok:
            logger.error('Zabbix send failed: processed=%s failed=%s error=%s', result.processed, result.failed, result.error)
        return result

    # main supplies the persistent path; embedders/tests may use an in-memory cycle.
    state = DiscoveryState(discovery_state_path, logger)
    discovery = state.pending(build_discovery(config), config.server, config.port)
    if discovery:
        result = send(discovery)
        if result.ok:
            try:
                state.acknowledge(discovery, config.server, config.port)
            except OSError as exc:
                errors += 1
                logger.error('Cannot save discovery cache; retrying next cycle: %s', exc)
    else:
        logger.info('Discovery unchanged; next heartbeat is due within one hour')
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
                event(logger, logging.ERROR, 'collection_failed', error=error, target=result.task, command=result.command)
            pending.extend(result.metrics)
        send(pending)
    event(logger, logging.INFO, 'cycle_end', processed=processed, failed=failed, unconfirmed=unconfirmed,
          collection_errors=errors, elapsed_seconds=round(monotonic() - started, 2))
    return 1 if failed or errors else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Collect Linux metrics and send to Zabbix')
    parser.add_argument('--config', help='YAML 或旧版 INI 配置文件路径')
    parser.add_argument('--check-config', action='store_true', help='Validate configuration without collecting or sending')
    parser.add_argument('--log-level', type=str.upper, choices=LEVELS, help='临时覆盖普通日志等级；审计始终完整记录')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.log_level:
            config = replace(config, log_level=args.log_level)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.check_config:
        from .yaml_config import describe_config
        print(describe_config(config))
        return 0
    if not sys.platform.startswith('linux'):
        print('Collection requires Linux; use --check-config on other platforms.', file=sys.stderr)
        return 2
    logger = None
    try:
        logger = setup_logging(ROOT / 'log', level=config.log_level, console=config.log_console, retention_days=config.log_retention_days)
        event(logger, logging.INFO, 'agent_start', config_requested=args.config or 'auto',
              log_level=config.log_level, console=config.log_console, retention_days=config.log_retention_days,
              log_path=str(ROOT / 'log/agent.log'), audit_path=str(ROOT / 'log/audit.jsonl'))
        logger.debug('Full audit mode: individual metric requests; increases request count')
        with process_lock(ROOT / 'log/agent.lock') as acquired:
            if not acquired:
                logger.warning('Previous cycle is still running; skipping')
                return 0
            return run_cycle(config, logger, discovery_state_path=ROOT / 'log/discovery-state.json')
    except Exception as exc:
        if logger is not None:
            logger.exception('Agent failed: %s: %s', type(exc).__name__, exc)
        else:
            print('Agent failed: {}: {}'.format(type(exc).__name__, exc), file=sys.stderr)
        return 1

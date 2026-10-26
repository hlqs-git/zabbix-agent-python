import json
import subprocess
from .command import error_summary, run_command


def network_snapshot():
    import psutil
    return psutil.net_io_counters(pernic=True), psutil.net_if_stats()


def get_net_io_counters(interface_name, snapshot=None):
    counters, stats = snapshot if snapshot is not None else network_snapshot()
    if interface_name not in counters or interface_name not in stats:
        raise ValueError('Invalid or disappeared interface: {}'.format(interface_name))
    counter = counters[interface_name]
    return counter.bytes_recv, counter.bytes_sent, int(stats[interface_name].isup)


def namespace_command(namespace, interface_name):
    return ['ip', 'netns', 'exec', namespace, 'ip', '-j', '-s', 'link', 'show', 'dev', interface_name]


def get_ns_net_io_counters(namespace, interface_name, command=None):
    command = namespace_command(namespace, interface_name) if command is None else command
    result = run_command(command,
                            capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise ValueError('Namespace interface command failed: {}'.format(error_summary(result.stderr.strip())))
    try:
        link = json.loads(result.stdout)[0]
        stats = link.get('stats64', link.get('stats'))
        rx, tx = int(stats['rx']['bytes']), int(stats['tx']['bytes'])
        if rx < 0 or tx < 0:
            raise ValueError('Negative interface counter')
        return rx, tx, int('UP' in link['flags'] and 'LOWER_UP' in link['flags'])
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid namespace interface statistics') from exc

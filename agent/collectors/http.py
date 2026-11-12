import os
import re
import subprocess
from ipaddress import IPv4Address
from .command import run_command, error_summary


def parse_httping(output):
    loss = re.search(r'([\d.]+)% failed', output)
    if not loss or not 0 <= float(loss.group(1)) <= 100:
        raise ValueError('httping output has no valid failure statistics')
    loss = float(loss.group(1))
    if loss == 100:
        return loss, 0.0
    delay = re.search(r'round-trip min/avg/max\s*=\s*[\d.]+/([\d.]+)/[\d.]+\s*ms', output)
    if not delay:
        raise ValueError('httping output has no valid RTT statistics')
    value = float(delay.group(1))
    import math
    if not math.isfinite(value):
        raise ValueError('Invalid httping latency')
    return loss, value


def httping_command(address, count=10, timeout=3, namespace=None, source_ip=None):
    command = ['httping', '-c', str(count), '-t', str(timeout)]
    if address.startswith('https://'):
        command.append('-l')
    if source_ip is not None:
        command.extend(['-y', str(IPv4Address(source_ip))])
    command.extend(['-g', address])
    if namespace:
        command = ['ip', 'netns', 'exec', namespace] + command
    return command


def httping(address, count=10, timeout=3, namespace=None, source_ip=None, command=None):
    command = httping_command(address, count, timeout, namespace, source_ip) if command is None else command
    result = run_command(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True, timeout=count * (timeout + 1) + 5,
                         env=dict(os.environ, LC_ALL='C'))
    try:
        return parse_httping(result.stdout)
    except ValueError as exc:
        raise ValueError('{}; exit={}; stderr={}'.format(error_summary(exc), result.returncode, error_summary(result.stderr))) from exc

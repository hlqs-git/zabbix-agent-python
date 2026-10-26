import os
import re
import subprocess
from ipaddress import IPv4Address


def parse_ping(output):
    loss = re.search(r'(\d+(?:\.\d+)?)% packet loss', output)
    if not loss:
        raise ValueError('ping output has no packet loss statistics')
    loss = float(loss.group(1))
    if not 0 <= loss <= 100:
        raise ValueError('Invalid packet loss')
    if loss == 100:
        return loss, 0.0
    rtt = re.search(r'(?:rtt|round-trip).*?=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+', output)
    if not rtt:
        raise ValueError('ping output has no RTT statistics')
    return loss, float(rtt.group(1))


def ping(ip, sec=50, interval='0.25', namespace=None, source_ip=None):
    command = ['ping', '-w', str(sec), '-i', str(interval), '-q']
    if source_ip is not None:
        command.extend(['-I', str(IPv4Address(source_ip))])
    command.append(ip)
    if namespace:
        command = ['ip', 'netns', 'exec', namespace] + command
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=sec + 5, env=dict(os.environ, LC_ALL='C'))
    if result.returncode not in (0, 1):
        raise ValueError('ping failed: {}'.format(result.stderr.strip()))
    return parse_ping(result.stdout)

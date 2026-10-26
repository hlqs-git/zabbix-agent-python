import json
import math
import subprocess
from pathlib import Path
from .command import error_summary, run_command


def parse_tcping(output):
    try:
        data = json.loads(output.strip().splitlines()[-1])
        if not isinstance(data, dict):
            raise ValueError('tcping output is not a statistics object')
        if data.get('type') != 'statistics':
            raise ValueError('tcping did not return statistics: ' + error_summary('{}: {}'.format(data.get('type', 'missing type'), data.get('message', 'No statistics'))))
        loss = float(data['total_packet_loss'])
        delay = 0.0 if loss == 100 else float(data['latency_avg'])
        if not 0 <= loss <= 100 or not math.isfinite(delay) or delay < 0:
            raise ValueError('Invalid tcping statistics')
        return data['addr'], loss, delay
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid or empty tcping output') from exc


def tcping_command(host, port, count=50, timeout=1, namespace=None):
    local_binary = Path(__file__).resolve().parents[2] / '.venv/bin/tcping'
    binary = str(local_binary) if local_binary.is_file() else '/usr/local/sbin/tcping'
    command = [binary, '-4', '-c', str(count), '-t', str(timeout), '-j', host, str(port)]
    if namespace:
        command = ['ip', 'netns', 'exec', namespace] + command
    return command


def tcping(host, port, count=50, timeout=1, namespace=None, command=None):
    command = tcping_command(host, port, count, timeout, namespace) if command is None else command
    result = run_command(command, capture_output=True, text=True,
                            timeout=count * (timeout + 1) + 5)
    # Some tcping versions exit nonzero on full loss; valid statistics remain usable.
    try:
        return parse_tcping(result.stdout)
    except ValueError as exc:
        raise ValueError('{}; exit={}; stderr={}'.format(error_summary(exc), result.returncode, error_summary(result.stderr.strip()))) from exc

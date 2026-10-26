import json
import math
import subprocess
from pathlib import Path


def parse_tcping(output):
    try:
        data = json.loads(output.strip().splitlines()[-1])
        if not isinstance(data, dict) or data.get('type') != 'statistics':
            raise ValueError('tcping did not return statistics: {}'.format(data))
        loss = float(data['total_packet_loss'])
        delay = 0.0 if loss == 100 else float(data['latency_avg'])
        if not 0 <= loss <= 100 or not math.isfinite(delay) or delay < 0:
            raise ValueError('Invalid tcping statistics')
        return data['addr'], loss, delay
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid or empty tcping output') from exc


def tcping(host, port, count=50, timeout=1, namespace=None):
    local_binary = Path(__file__).resolve().parents[2] / '.venv/bin/tcping'
    binary = str(local_binary) if local_binary.is_file() else '/usr/local/sbin/tcping'
    command = [binary, '-4', '-c', str(count), '-t', str(timeout), '-j', host, str(port)]
    if namespace:
        command = ['ip', 'netns', 'exec', namespace] + command
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=count * (timeout + 1) + 5)
    # Some tcping versions exit nonzero on full loss; valid statistics remain usable.
    try:
        return parse_tcping(result.stdout)
    except ValueError as exc:
        raise ValueError('{}; exit={}; stderr={}'.format(exc, result.returncode, result.stderr.strip())) from exc

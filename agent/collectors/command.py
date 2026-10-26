import logging
import subprocess
from time import monotonic
from ..audit import event

logger = logging.getLogger('agent.collectors.command')


def error_summary(value):
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    return str(value or '')[:512]


def run_command(command, **kwargs):
    started = monotonic()
    event(logger, logging.DEBUG, 'command_start', command=command, timeout=kwargs.get('timeout'))
    try:
        result = subprocess.run(command, **kwargs)
    except Exception as exc:
        event(logger, logging.DEBUG, 'command_error', command=command,
              elapsed_ms=round((monotonic() - started) * 1000, 3),
              error_type=type(exc).__name__, error=str(exc),
              error_summary=error_summary(getattr(exc, 'stderr', None)))
        logger.debug('Command exception stack', exc_info=True)
        raise
    event(logger, logging.DEBUG, 'command_result', command=command,
          returncode=result.returncode, error_summary=error_summary(getattr(result, 'stderr', '')),
          elapsed_ms=round((monotonic() - started) * 1000, 3))
    return result

import logging
import subprocess
from time import monotonic
from ..audit import event

logger = logging.getLogger('agent.collectors.command')


def run_command(command, **kwargs):
    started = monotonic()
    event(logger, logging.DEBUG, 'command_start', command=command, timeout=kwargs.get('timeout'))
    try:
        result = subprocess.run(command, **kwargs)
    except Exception as exc:
        event(logger, logging.DEBUG, 'command_error', command=command,
              elapsed_ms=round((monotonic() - started) * 1000, 3),
              error_type=type(exc).__name__, error=str(exc),
              stdout=getattr(exc, 'stdout', None), stderr=getattr(exc, 'stderr', None))
        logger.debug('Command exception stack', exc_info=True)
        raise
    event(logger, logging.DEBUG, 'command_result', command=command,
          returncode=result.returncode, stdout=result.stdout, stderr=getattr(result, 'stderr', ''),
          elapsed_ms=round((monotonic() - started) * 1000, 3))
    return result

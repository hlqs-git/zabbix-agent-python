import logging
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from logging.handlers import TimedRotatingFileHandler


LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


class DailyFileHandler(TimedRotatingFileHandler):
    def getFilesToDelete(self):
        cutoff = datetime.now().date() - timedelta(days=self.backupCount)
        base = Path(self.baseFilename)
        expired = set()
        for path in base.parent.glob(base.name + '.*'):
            suffix = path.name[len(base.name) + 1:]
            try:
                day = datetime.strptime(suffix, '%Y-%m-%d').date()
            except ValueError:
                continue
            if day.strftime('%Y-%m-%d') != suffix:
                continue
            if path.is_file() and day < cutoff:
                expired.add(str(path))
        return sorted(expired)


class JsonFormatter(logging.Formatter):
    def __init__(self, run_id):
        super().__init__()
        self.run_id = run_id

    def format(self, record):
        data = {'time': datetime.fromtimestamp(record.created).astimezone().isoformat(timespec='milliseconds'),
                'level': record.levelname, 'run_id': self.run_id, 'pid': record.process,
                'thread': record.threadName, 'logger': record.name,
                'event': getattr(record, 'event', 'message'), 'message': record.getMessage()}
        if hasattr(record, 'fields'):
            data['fields'] = record.fields
        if record.exc_info:
            data['exception'] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def setup_logging(directory, level='INFO', console=True, retention_days=14, run_id=None):
    level = level.upper()
    if level not in LEVELS:
        raise ValueError('Invalid log level: ' + level)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('agent')
    logger.setLevel(level)
    logger.propagate = False
    for handler in logger.handlers[:]:
        if getattr(handler, '_agent_owned', False):
            logger.removeHandler(handler)
            handler.close()
    formatter = JsonFormatter(run_id or uuid4().hex)
    handler = DailyFileHandler(str(directory / 'agent.log'), when='midnight', backupCount=retention_days, encoding='utf-8')
    try:
        for expired in handler.getFilesToDelete():
            os.remove(expired)
    except Exception:
        handler.close()
        raise
    handlers = [handler]
    if console:
        stream = logging.StreamHandler()
        handlers.append(stream)
    for handler in handlers:
        handler._agent_owned = True
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

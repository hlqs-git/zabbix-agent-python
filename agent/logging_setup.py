import logging
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from logging.handlers import TimedRotatingFileHandler
from .readable_logs import ReadableFilter, ReadableFormatter


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


class AuditFilter(logging.Filter):
    """Delivery already contains the send payload and parsed response."""

    def filter(self, record):
        return getattr(record, 'event', None) not in {'metric_send', 'zabbix_response'}


class JsonFormatter(logging.Formatter):
    def __init__(self, run_id):
        super().__init__()
        self.run_id = run_id

    def format(self, record):
        data = {'time': datetime.fromtimestamp(record.created).astimezone().isoformat(timespec='milliseconds'),
                'level': record.levelname, 'run_id': self.run_id, 'pid': record.process,
                'thread': record.threadName, 'logger': record.name,
                'event': getattr(record, 'event', 'message')}
        message = record.getMessage()
        if message != data['event']:
            data['message'] = message
        if hasattr(record, 'fields'):
            # Records are shared with the readable handlers; never mutate them.
            fields = dict(record.fields)
            if data['event'] == 'metric_delivery' and fields.get('error') == '':
                del fields['error']
            data['fields'] = fields
        if record.exc_info:
            data['exception'] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str).replace('\u0085', '\\u0085').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def setup_logging(directory, level='INFO', console=True, retention_days=14, run_id=None):
    level = level.upper()
    if level not in LEVELS:
        raise ValueError('Invalid log level: ' + level)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('agent')
    # Capture all audit events; human-facing handlers apply the chosen level.
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in logger.handlers[:]:
        if getattr(handler, '_agent_owned', False):
            logger.removeHandler(handler)
            handler.close()
    identifier = run_id or uuid4().hex
    readable = ReadableFormatter(identifier)
    audit = JsonFormatter(identifier)
    try:
        for filename, formatter, project in (('agent.log', readable, True), ('audit.jsonl', audit, False)):
            handler = DailyFileHandler(str(directory / filename), when='midnight', backupCount=retention_days, encoding='utf-8')
            handler._agent_owned = True
            handler.setLevel(level if project else logging.DEBUG)
            handler.setFormatter(formatter)
            if project:
                handler.addFilter(ReadableFilter())
            else:
                handler.addFilter(AuditFilter())
            logger.addHandler(handler)
            for expired in handler.getFilesToDelete():
                os.remove(expired)
        if console:
            stream = logging.StreamHandler()
            stream._agent_owned = True
            stream.setLevel(level)
            stream.setFormatter(readable)
            stream.addFilter(ReadableFilter())
            logger.addHandler(stream)
    except Exception:
        for handler in logger.handlers[:]:
            if getattr(handler, '_agent_owned', False):
                logger.removeHandler(handler)
                handler.close()
        raise
    return logger

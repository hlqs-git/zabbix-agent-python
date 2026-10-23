import logging
from logging.handlers import TimedRotatingFileHandler


def setup_logging(directory):
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('agent')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = TimedRotatingFileHandler(str(directory / 'agent.log'), when='midnight', backupCount=14, encoding='utf-8')
        handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
        logger.addHandler(handler)
        stream = logging.StreamHandler()
        stream.setFormatter(handler.formatter)
        logger.addHandler(stream)
    return logger

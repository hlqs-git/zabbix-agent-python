"""Legacy logger accessor. Initialization belongs to agent.app."""
import logging


class Log:
    def __init__(self, logger=None, log_cate='search'):
        self.logger = logging.getLogger('agent' + ('.' + logger if logger else ''))

    def getlog(self):
        return self.logger

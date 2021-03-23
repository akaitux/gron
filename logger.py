import logging
import logging.handlers
import os
import sys


class LevelFilter(logging.Filter):
    def __init__(self, from_level, to_level=999999999):
        self.from_level = from_level 
        self.to_level = to_level 

    def filter(self, record):
        if record.levelno >= self.from_level and record.levelno < self.to_level:
            return True
        else:
            return False

def setup(options):
    # options must be options = {'debug': False, 'silent': False}
    fr = "%(message)s"
    stdout_handler = logging.StreamHandler(sys.stdout)
    if options.get('debug'):
        stdout_filter = LevelFilter(logging.DEBUG, logging.CRITICAL) 
    else:
        stdout_filter = LevelFilter(logging.INFO, logging.CRITICAL) 
    stdout_handler.addFilter(stdout_filter)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_filter = LevelFilter(logging.ERROR) 
    stderr_handler.addFilter(stderr_filter)
    handlers = [stdout_handler,stderr_handler]
    if not options['silent']:
        logging.basicConfig(level=options.get('debug') and logging.DEBUG or logging.INFO, format=fr,
                           handlers=handlers)
    else:
        logging.basicConfig(level=logging.WARNING, format=fr, stream=sys.stderr)

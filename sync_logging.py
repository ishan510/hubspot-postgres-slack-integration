"""Small rotating run log. Never pass credentials or contact data to the logger."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
import uuid


def configure_logging():
    directory = Path(__file__).parent / 'logs'
    directory.mkdir(exist_ok=True)
    logger = logging.getLogger('acme_sync')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for old in logger.handlers[:]:
        logger.removeHandler(old)
        old.close()
    handler = RotatingFileHandler(directory / 'sync.log', maxBytes=1_000_000, backupCount=3)
    run_id = uuid.uuid4().hex[:12]
    formatter = logging.Formatter(f'%(asctime)sZ level=%(levelname)s run_id={run_id} %(message)s',
                                  datefmt='%Y-%m-%dT%H:%M:%S')
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

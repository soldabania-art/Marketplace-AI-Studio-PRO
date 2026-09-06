import logging, sys, traceback
from logging.handlers import RotatingFileHandler
from .core import DATA

LOG_DIR=DATA/'logs'
LOG_FILE=LOG_DIR/'app.log'


def setup_logging():
    LOG_DIR.mkdir(parents=True,exist_ok=True)
    root=logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h,RotatingFileHandler) for h in root.handlers):
        handler=RotatingFileHandler(LOG_FILE,maxBytes=2_000_000,backupCount=5,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        root.addHandler(handler)
    logging.getLogger(__name__).info('Application logging initialized')
    return LOG_FILE


def install_exception_hook():
    old=sys.excepthook
    def hook(exc_type,exc_value,exc_tb):
        logging.getLogger('crash').critical('Unhandled exception',exc_info=(exc_type,exc_value,exc_tb))
        try:old(exc_type,exc_value,exc_tb)
        except Exception:pass
    sys.excepthook=hook


def log_exception(area,error):
    logging.getLogger(str(area)).exception(str(error))


def log_path():
    LOG_DIR.mkdir(parents=True,exist_ok=True)
    return LOG_FILE

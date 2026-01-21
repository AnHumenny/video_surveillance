import logging
import os
from datetime import datetime
import sys


class HypercornFilter(logging.Filter):
    """Filter out Hypercorn access logs"""

    def filter(self, record):
        return not record.name.startswith('hypercorn.access')

_logs_base_dir = None


def get_logs_directory():
    """Get or create logs directory with current date."""
    global _logs_base_dir

    if _logs_base_dir is None:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        current_date = datetime.now().strftime("%Y-%m-%d")
        _logs_base_dir = os.path.join(base_dir, "logs", current_date)
        os.makedirs(_logs_base_dir, exist_ok=True)

    return _logs_base_dir


def setup_celery_logging():
    """Setup logging specifically for Celery."""
    log_dir = get_logs_directory()

    celery_logger = logging.getLogger('celery')
    celery_logger.setLevel(logging.INFO)

    celery_logger.handlers = []

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    log_file = os.path.join(log_dir, "celery.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(HypercornFilter())

    celery_logger.addHandler(file_handler)
    celery_logger.addHandler(console_handler)
    celery_logger.propagate = False

    for logger_name in ['celery.worker', 'celery.beat']:
        logger = logging.getLogger(logger_name)
        logger.handlers = []

        component_file = os.path.join(log_dir, f"{logger_name.replace('.', '_')}.log")
        component_handler = logging.FileHandler(component_file, encoding='utf-8')
        component_handler.setFormatter(formatter)
        component_handler.setLevel(logging.INFO)

        logger.addHandler(component_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

    return celery_logger


def get_logger(name=None):
    """Get a logger with date-based file output."""
    logger_name = name or __name__
    logger = logging.getLogger(logger_name)

    if logger_name.startswith('celery'):
        return setup_celery_logging()

    if not logger.handlers:
        log_dir = get_logs_directory()

        if logger_name == '__main__':
            log_filename = "main.log"
        elif '.' in logger_name:
            log_filename = f"{logger_name.split('.')[-1]}.log"
        else:
            log_filename = f"{logger_name}.log"

        log_file = os.path.join(log_dir, log_filename)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        console_handler.addFilter(HypercornFilter())

        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

    return logger


app_logger = get_logger('app')

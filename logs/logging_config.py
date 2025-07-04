import logging


class HypercornFilter(logging.Filter):
    """filtered hypercorn"""
    def filter(self, record):
        return not record.name.startswith('hypercorn')

def setup_logging():
    """Setting logger."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )

        for handler in logging.getLogger().handlers:
            handler.addFilter(HypercornFilter())
        logging.getLogger('hypercorn').setLevel(logging.ERROR)

setup_logging()

logger = logging.getLogger(__name__)
import logging
from pathlib import Path

from rich.logging import RichHandler
from textual.widgets import RichLog

log_path = Path(__file__).resolve().parent.parent / "logs"
Path(log_path).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_time=False, markup=True, console=None)],
)


class LogUtil:
    def __init__(self, rich_log_widget: RichLog):
        self.rich_log_widget = rich_log_widget

    def log(self, message: str):
        self.rich_log_widget.write(message)
        logging.info(message)

    def log_error(self, message: str):
        self.rich_log_widget.write(message)
        logging.error(message)

    def log_warning(self, message: str):
        self.rich_log_widget.write(message)
        logging.warning(message)


class RichLogWriter:
    def __init__(self, log_util: LogUtil):
        self.log_util = log_util

    def write(self, message):
        if message.strip():
            self.log_util.log(message.rstrip())

    def flush(self):
        pass  # Needed for compatibility

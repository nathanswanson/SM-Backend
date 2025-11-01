import logging
import logging.config

from server_manager.webservice.util.singleton import SingletonMeta

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(message)s",
            "datefmt": "[%X]",
        },
    },
    "handlers": {
        "default": {
            "level": "DEBUG",
            "formatter": "standard",
            "class": "rich.logging.RichHandler",
            "rich_tracebacks": True,
            "markup": False,
            "show_time": True,
            "show_level": True,
            "show_path": False,
            "log_time_format": "[%X]",
        },
        "fallback": {
            "level": "DEBUG",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "server-manager": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
        "__main__": {  # if __name__ == '__main__'
            "handlers": ["default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "uvicorn.asgi": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
}


class SMLogger(metaclass=SingletonMeta):
    def __init__(self):
        root_logger = logging.getLogger()
        logging.config.dictConfig(LOG_CONFIG)
        root_logger.setLevel("DEBUG")
        self.logger = logging.getLogger("server-manager")
        self.logger.setLevel("DEBUG")

    def debug(self, msg: str, *args, **kwargs):
        message = f"\x1b[90m\x1b[3m{msg}\x1b[0m"
        self.logger.debug(message, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        message = f"\x1b[33m{msg}\x1b[0m"
        self.logger.warning(message, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        message = f"\x1b[31m{msg}\x1b[0m"
        self.logger.critical(message, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        message = f"\x1b[31m{msg}\x1b[0m"
        self.logger.exception(message, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        message = f"\x1b[31m{msg}\x1b[0m"
        self.logger.error(message, *args, **kwargs)

    def log_group(self, message: str, child_messages):
        full_message = message + "\n"
        for child_message in child_messages:
            full_message += f"┕   {child_message}\n"
        self.info(full_message)


sm_logger: SMLogger = SMLogger()

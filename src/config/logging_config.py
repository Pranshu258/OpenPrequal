import logging
import logging.config
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = os.getenv("LOG_FILE", "logs/openprequal.log")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": LOG_FORMAT,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": LOG_LEVEL,
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": LOG_FILE,
            "formatter": "default",
            "level": LOG_LEVEL,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": LOG_LEVEL,
    },
}


def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)

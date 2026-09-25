from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import enum
import logging
import os
import sys

from loguru import logger

from main.appodus_utils import Utils


class LogLevel(str, enum.Enum):
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


class _InterceptHandler(logging.Handler):
    """Hands a stdlib record to loguru, keeping its level, caller and traceback."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Libraries that log ordinary outcomes above their weight. The JWT library logs every 401
# (an expired or revoked token) at ERROR before raising; the handler already records those at
# WARNING, so its own lines are only noise.
_QUIET_LIBRARIES = {"libre_fastapi_jwt": logging.CRITICAL}


def route_stdlib_logging(level: str) -> None:
    """Send every stdlib logger (APScheduler, httpx, the messaging resilience layer) to loguru's
    sinks — the app's format and log file — at *level*, with the noisy libraries quieted.

    SQLAlchemy's `echo` installs its own stdout handler, so it is kept from propagating as well,
    or each statement would print twice.
    """
    logging.basicConfig(handlers=[_InterceptHandler()], level=level, force=True)
    for name, library_level in _QUIET_LIBRARIES.items():
        logging.getLogger(name).setLevel(library_level)
    logging.getLogger("sqlalchemy").propagate = False


class LoggerFactory:

    def __init__(self):
        self._app_name = Utils.get_from_env_fail_if_not_exists("BRAND")
        self._log_level = Utils.get_from_env_fail_if_not_exists("LOG_LEVEL")
        self._logger_file_name = Utils.get_from_env_fail_if_not_exists("LOGGER_FILE")
        self._logger_file_path = Utils.get_from_env_fail_if_not_exists("LOGGER_FILE_PATH")

        self._logger_file = self._set_logger_file()
        self._init_logger()

    def _make_duplicate_filter(self):
        last_log = {}

        def duplicate_filter(record):
            current_log = (record["name"], record["level"].no, record["message"])
            if current_log != last_log.get("last"):
                last_log["last"] = current_log
                return True
            return False

        return duplicate_filter

    def _init_logger(self):
        log_level = self._log_level if self._log_level in set(LogLevel) else LogLevel.INFO
        fmt = "{time:YYYY-MM-DD HH:mm:ss} " + self._app_name + " {level}: {message}"
        duplicate_filter = self._make_duplicate_filter()

        # Remove default handler
        logger.remove()

        # Console handler. Reconfigure stdout to UTF-8 (replacing any un-encodable
        # char) so log content with non-ASCII characters (e.g. "↔") never crashes the
        # sink on a Windows cp1252 console.
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
        logger.add(
            sys.stdout,
            level=log_level,
            format=fmt,
            filter=duplicate_filter
        )

        # File handler
        logger.add(
            self._logger_file,
            level=log_level,
            format=fmt,
            filter=duplicate_filter,
            encoding="utf-8",
            rotation="10 MB",
            retention="14 days",
        )

        route_stdlib_logging(log_level)

        # # file rotation
        # logger.add(
        #     self._logger_file,
        #     rotation="10 MB",
        #     retention="14 days",
        # )

    def get_logger(self) -> Logger:
        return logger

    def _set_logger_file(self) -> str:
        logger_file = os.path.join(self._logger_file_path, self._logger_file_name)
        if not os.path.exists(logger_file):
            try:
                os.makedirs(logger_file.removesuffix(self._logger_file_name))
            except FileExistsError:
                print("Log file already exists")
        return str(logger_file)


# di['logger'] = lambda _di: LoggerFactory().get_logger()
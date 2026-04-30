from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import enum
import os
import sys

from loguru import logger

from main.appodus_utils import Utils


class LogLevel(str, enum.Enum):
    DEBUG = 'DEBUG'
    INFO = 'INFO'


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
        log_level = self._log_level if self._log_level in (LogLevel.DEBUG, LogLevel.INFO) else LogLevel.INFO
        fmt = "{time:YYYY-MM-DD HH:mm:ss} " + self._app_name + " {level}: {message}"
        duplicate_filter = self._make_duplicate_filter()

        # Remove default handler
        logger.remove()

        # Console handler
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
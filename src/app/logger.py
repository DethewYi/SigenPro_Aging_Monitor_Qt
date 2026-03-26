import logging
import os
from datetime import datetime
from PyQt6.QtCore import QtMsgType


class Logger:
    """Application-wide logger with Qt message handler integration."""

    _instance = None
    MAX_LOG_FILES = 30
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    def __init__(self):
        self._log_dir = ""
        self._current_file = None
        self._file_handler = None
        self._log_level = logging.INFO

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_log_dir(self, log_dir):
        """Set the log output directory and start a new rotating file handler."""
        self._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._setup_file_handler()

    def _setup_file_handler(self):
        if self._file_handler:
            logging.root.removeHandler(self._file_handler)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self._log_dir, f"aging_monitor_{timestamp}.log")

        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(self._log_level)
        formatter = logging.Formatter(
            '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(thread)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
        self._file_handler = handler
        self._current_file = log_file

        logging.root.setLevel(self._log_level)

    @staticmethod
    def qt_message_handler(msg_type, context, message):
        """Bridge Qt log messages into the Python logging framework."""
        level = {
            QtMsgType.QtDebugMsg: logging.DEBUG,
            QtMsgType.QtInfoMsg: logging.INFO,
            QtMsgType.QtWarningMsg: logging.WARNING,
            QtMsgType.QtCriticalMsg: logging.ERROR,
            QtMsgType.QtFatalMsg: logging.CRITICAL,
        }.get(msg_type, logging.INFO)
        logger = logging.getLogger("Qt")
        logger.log(level, f"{message}")
        if msg_type == QtMsgType.QtFatalMsg:
            raise SystemExit(1)

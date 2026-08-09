"""Logging configuration shared across the whole app.

Every log line is formatted as "[YYYY-MM-DD hh:mm:ss.sss][module.submodule.func] message",
and lines are written both to the console and to a file under the repo's logs/ directory.
"""

import logging
from pathlib import Path

_LOG_FORMAT = "[%(asctime)s][%(name)s.%(funcName)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _MillisecondFormatter(logging.Formatter):
    # stdlib logging joins seconds and milliseconds with a comma by default; we want a period.
    default_msec_format = "%s.%03d"


def setup_logging(log_dir: Path, log_file: str = "blunder.log", level: int = logging.INFO) -> None:
    """Configure the root logger with a console handler and a file handler under log_dir."""
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = _MillisecondFormatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = logging.FileHandler(log_dir / log_file)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Thin wrapper around logging.getLogger for consistent import style across the package."""
    return logging.getLogger(name)

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path.home() / ".cache" / "steamdc"
LOG_FILE = LOG_DIR / "steamdc.log"
_MAX_BYTES = 1_048_576
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    logging.getLogger(__name__).info("Logging initialized, file: %s", LOG_FILE)

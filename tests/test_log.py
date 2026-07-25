from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

from steamdc.log import LOG_DIR, LOG_FILE, setup_logging


class TestSetupLogging:
    def test_creates_directory_and_handler(self, tmp_path: Path):
        log_dir = tmp_path / "steamdc"
        log_file = log_dir / "steamdc.log"
        with patch("steamdc.log.LOG_DIR", log_dir):
            with patch("steamdc.log.LOG_FILE", log_file):
                setup_logging()

        assert log_dir.exists()
        assert log_dir.is_dir()

        root = logging.getLogger()
        assert any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            for h in root.handlers
        )

    def test_handler_writes_to_disk(self, tmp_path: Path):
        log_dir = tmp_path / "steamdc"
        log_file = log_dir / "steamdc.log"
        with patch("steamdc.log.LOG_DIR", log_dir):
            with patch("steamdc.log.LOG_FILE", log_file):
                setup_logging()

        logger = logging.getLogger("test_logger")
        logger.info("hello world")

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "hello world" in content

    def test_rotating_handler_config(self, tmp_path: Path):
        log_dir = tmp_path / "steamdc"
        log_file = log_dir / "steamdc.log"
        with patch("steamdc.log.LOG_DIR", log_dir):
            with patch("steamdc.log.LOG_FILE", log_file):
                setup_logging()

        root = logging.getLogger()
        handlers = [
            h
            for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(handlers) >= 1
        h = handlers[0]
        assert h.maxBytes == 1_048_576
        assert h.backupCount == 3
        assert h.encoding == "utf-8"
        assert h.level == logging.NOTSET
        assert root.level == logging.DEBUG

    def test_logging_constants(self):
        assert str(LOG_FILE).endswith("steamdc.log")
        assert LOG_DIR.name == "steamdc"

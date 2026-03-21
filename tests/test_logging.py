from __future__ import annotations

import logging

from app.core.logging import configure_logging, get_logger


def test_configure_logging_dev_mode() -> None:
    configure_logging(log_level="WARNING", json_logs=False)
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_json_mode() -> None:
    configure_logging(log_level="ERROR", json_logs=True)
    assert logging.getLogger().level == logging.ERROR


def test_get_logger_returns_logger() -> None:
    log = get_logger(__name__)
    assert log is not None

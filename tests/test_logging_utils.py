from __future__ import annotations

import logging

from file_migration.logging_utils import configure_logging


def test_configure_logging_uses_plain_formatter() -> None:
    root_logger = logging.getLogger()
    previous_handlers = list(root_logger.handlers)
    previous_level = root_logger.level
    root_logger.handlers = []

    try:
        configure_logging()

        assert len(root_logger.handlers) == 1
        formatter = root_logger.handlers[0].formatter
        assert formatter is not None
        record = logging.LogRecord(
            name="file_migration.cli",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="plain message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        assert "plain message" in formatted
        assert "[flow=" not in formatted
        assert "job=" not in formatted
        assert "kind=" not in formatted
    finally:
        root_logger.handlers = previous_handlers
        root_logger.setLevel(previous_level)

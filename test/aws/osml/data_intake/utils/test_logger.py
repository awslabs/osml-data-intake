#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

import logging
from unittest.mock import patch

from aws.osml.data_intake.utils.logger import _LOG_CONTEXT, AsyncContextFilter, configure_logger, get_logger


class TestLogger:
    def test_logger_no_handlers(self):
        """
        Test that basicConfig is called if no handlers are present on the root logger.
        """
        with patch("logging.Logger.hasHandlers", return_value=False), patch("logging.basicConfig") as mock_basic_config:
            logger = get_logger("test_logger", logging.DEBUG)

            mock_basic_config.assert_called_once_with(level=logging.DEBUG)
            assert logger.name == "test_logger"

    def test_logger_with_handlers(self):
        """
        Test that basicConfig is not called if handlers are present on the root logger.
        """
        with patch("logging.Logger.hasHandlers", return_value=True), patch("logging.basicConfig") as mock_basic_config:
            logger = get_logger("test_logger", logging.DEBUG)

            mock_basic_config.assert_not_called()
            assert logger.name == "test_logger"

    def test_configure_logger(self):
        """
        Test the configure_logger function.
        """
        from pythonjsonlogger.json import JsonFormatter

        logger = logging.getLogger("test_configure_logger")

        formatter = JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(image_hash)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
        )
        filter = AsyncContextFilter(attribute_names=["image_hash"])

        configured_logger = configure_logger(logger, logging.INFO, log_formatter=formatter, log_filter=filter)

        stream_handler_exists = any(isinstance(handler, logging.StreamHandler) for handler in configured_logger.handlers)
        assert stream_handler_exists

        for handler in configured_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                assert handler.formatter == formatter

        assert filter in configured_logger.filters
        assert not configured_logger.propagate

    def test_async_context_filter(self):
        """
        Test the AsyncContextFilter class.
        """
        filter = AsyncContextFilter(attribute_names=["image_hash"])

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=0, msg="Test message", args=(), exc_info=None
        )
        _LOG_CONTEXT.set({"image_hash": "123456"})

        assert filter.filter(record)
        assert record.image_hash == "123456"

        _LOG_CONTEXT.set({})
        assert filter.filter(record)
        assert record.image_hash is None

    def test_set_context(self):
        """
        Test the set_context static method of AsyncContextFilter.
        """
        context = {"key": "value"}
        AsyncContextFilter.set_context(context)
        assert _LOG_CONTEXT.get() == context

        AsyncContextFilter.set_context(None)
        assert _LOG_CONTEXT.get() == {}

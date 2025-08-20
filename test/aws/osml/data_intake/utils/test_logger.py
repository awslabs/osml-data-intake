#  Copyright 2024-2025 Amazon.com, Inc. or its affiliates.

import logging
import unittest
from unittest.mock import patch


class TestLambdaLogger(unittest.TestCase):
    @patch("logging.Logger.hasHandlers", return_value=False)
    @patch("logging.basicConfig")
    def test_logger_no_handlers(self, mock_basic_config, mock_has_handlers):
        """
        Test that basicConfig is called if no handlers are present on the root logger.
        """
        from aws.osml.data_intake.utils.logger import get_logger

        logger = get_logger("test_logger", logging.DEBUG)

        # Check that basicConfig was called correctly
        mock_basic_config.assert_called_once_with(level=logging.DEBUG)

        # Check that the logger returned has the correct name
        self.assertEqual(logger.name, "test_logger")

    @patch("logging.Logger.hasHandlers", return_value=True)
    @patch("logging.basicConfig")
    def test_logger_with_handlers(self, mock_basic_config, mock_has_handlers):
        """
        Test that basicConfig is called if handlers are present on the root logger.
        """
        from aws.osml.data_intake.utils.logger import get_logger

        logger = get_logger("test_logger", logging.DEBUG)

        # Check that basicConfig was not called
        mock_basic_config.assert_not_called()

        # Check that the logger returned has the correct name
        self.assertEqual(logger.name, "test_logger")

    def test_configure_logger(self):
        """
        Test the configure_logger function.
        """
        from pythonjsonlogger.json import JsonFormatter

        from aws.osml.data_intake.utils.logger import AsyncContextFilter, configure_logger

        logger = logging.getLogger("test_configure_logger")

        formatter = JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(image_hash)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
        )
        filter = AsyncContextFilter(attribute_names=["image_hash"])

        configured_logger = configure_logger(logger, logging.INFO, log_formatter=formatter, log_filter=filter)

        # Check if the StreamHandler was added
        stream_handler_exists = any(isinstance(handler, logging.StreamHandler) for handler in configured_logger.handlers)
        self.assertTrue(stream_handler_exists)

        # Check if the formatter was set
        for handler in configured_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                self.assertEqual(handler.formatter, formatter)

        # Check if the filter was added
        self.assertIn(filter, configured_logger.filters)

        self.assertFalse(configured_logger.propagate)

    def test_async_context_filter(self):
        """
        Test the AsyncContextFilter class.
        """
        from aws.osml.data_intake.utils.logger import _LOG_CONTEXT, AsyncContextFilter

        filter = AsyncContextFilter(attribute_names=["image_hash"])

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=0, msg="Test message", args=(), exc_info=None
        )
        _LOG_CONTEXT.set({"image_hash": "123456"})

        self.assertTrue(filter.filter(record))
        self.assertEqual(record.image_hash, "123456")

        # Test without context
        _LOG_CONTEXT.set({})
        self.assertTrue(filter.filter(record))
        self.assertIsNone(record.image_hash)

    def test_set_context(self):
        """
        Test the set_context static method of AsyncContextFilter.
        """
        from aws.osml.data_intake.utils.logger import _LOG_CONTEXT, AsyncContextFilter

        context = {"key": "value"}
        AsyncContextFilter.set_context(context)
        self.assertEqual(_LOG_CONTEXT.get(), context)

        AsyncContextFilter.set_context(None)
        self.assertEqual(_LOG_CONTEXT.get(), {})


if __name__ == "__main__":
    unittest.main()

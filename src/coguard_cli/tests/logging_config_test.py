"""
Tests for the logging configuration shared by the entry points of the CLI.
"""

import logging
import unittest
import unittest.mock
from coguard_cli.logging_config import COGUARD_LOGGING_FORMAT, LOGGING_LEVELS, \
    set_logging_config

class TestLoggingConfig(unittest.TestCase):
    """
    The class for testing the shared logging configuration.
    """

    def test_set_logging_config(self):
        """
        Every accepted level is applied with the format of the CLI.
        """
        with unittest.mock.patch(
                'coguard_cli.logging_config.logging.basicConfig'
        ) as basic_config:
            for level in LOGGING_LEVELS:
                set_logging_config(level)
        self.assertEqual(
            [call.kwargs for call in basic_config.call_args_list],
            [{"format": COGUARD_LOGGING_FORMAT, "level": getattr(logging, level)}
             for level in LOGGING_LEVELS]
        )

    def test_set_logging_config_unknown_level(self):
        """
        A level which is not one of the accepted ones is refused.
        """
        with unittest.mock.patch(
                'coguard_cli.logging_config.logging.basicConfig'
        ) as basic_config:
            with self.assertRaises(ValueError):
                set_logging_config("NONSENSE")
            with self.assertRaises(ValueError):
                set_logging_config("debug")
        basic_config.assert_not_called()

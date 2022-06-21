"""
Tests for the auth.config class.
"""

import unittest
from coguard_cli.auth.auth_config import CoGuardCliConfig

class TestAuthClass(unittest.TestCase):
    """
    The class for testing the auth module.
    """

    def test_initialization_and_value_setting(self):
        """
        The testing of the correct initialization of the coguard-cli
        configuration.
        """
        conf = CoGuardCliConfig(
            "bar",
            "foo",
            "portal.coguard.io"
        )
        self.assertEqual(conf.get_password(), "foo")
        self.assertEqual(conf.get_username(), "bar")
        self.assertEqual(conf.get_coguard_url(), "portal.coguard.io")

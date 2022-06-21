"""
This module tests the configuration file finder factory.
"""

import unittest
from coguard_cli.image_check.config_file_finder_factory import config_file_finder_factory

class TestConfigFileFinderFactory(unittest.TestCase):
    """
    The test class for the ConfigFileFinderFactory
    """

    def test_generator(self):
        """
        Tests that the factory produces results and takes samples.
        """
        result = list(config_file_finder_factory())
        self.assertGreater(len(result), 0)
        self.assertTrue(any(finder_class.get_service_name() == "nginx"
                            for finder_class in result))

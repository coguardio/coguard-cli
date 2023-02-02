"""
This module tests the configuration file finder factory.
"""

import unittest
from coguard_cli.discovery.cloud_discovery.cloud_provider_factory import cloud_provider_factory

class TestCloudProviderFactory(unittest.TestCase):
    """
    The test class for the CloudProviderFactory
    """

    def test_generator(self):
        """
        Tests that the factory produces results and takes samples.
        """
        result = list(cloud_provider_factory())
        self.assertGreater(len(result), 0)
        self.assertTrue(any(finder_class.get_cloud_provider_name() == "aws"
                            for finder_class in result))

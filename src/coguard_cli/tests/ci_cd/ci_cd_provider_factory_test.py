"""
Tests for the CI/CD provider factory.
"""

import unittest
from coguard_cli.ci_cd.ci_cd_provider_factory import ci_cd_provider_factory

class TestCloudProviderFactory(unittest.TestCase):
    """
    The test class for the CloudProviderFactory
    """

    def test_generator(self):
        """
        Tests that the factory produces results and takes samples.
        """
        result = list(ci_cd_provider_factory())
        self.assertGreater(len(result), 0)
        self.assertTrue(any(finder_class.get_identifier() == "github"
                            for finder_class in result))

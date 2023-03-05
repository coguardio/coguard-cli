"""
This module contains tests for the GitHub Actions CI/CD provider
"""

import unittest
from coguard_cli.ci_cd.ci_cd_providers.ci_cd_provider_github import CiCdProviderGitHub

class TestCiCdProviderGitHub(unittest.TestCase):
    """
    The test class for the CloudProviderFactory
    """

    def test_add_not_existent(self):
        """
        The generation of the CI/CD script.
        """
        with unittest.mock.patch(
                'pathlib.Path.mkdir'
        ) as mkdir_path, \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: True
        ):
            provider = CiCdProviderGitHub()
            return_val = provider.add("foo")
            self.assertIsNone(return_val)
            mkdir_path.assert_called_once()

    def test_add_existent(self):
        """
        The generation of the CI/CD script.
        """
        with unittest.mock.patch(
                'pathlib.Path.mkdir'
        ) as mkdir_path, \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: False
        ), \
        unittest.mock.patch(
            'pathlib.Path.write_bytes'
        ) as writer, \
        unittest.mock.patch(
            'pathlib.Path.read_bytes'
        ) as reader:
            provider = CiCdProviderGitHub()
            return_val = provider.add("foo")
            self.assertEqual(return_val, "foo/.github/workflows")
            self.assertIsNotNone(return_val)
            mkdir_path.assert_called_once()
            writer.assert_called_once()
            reader.assert_called_once()

    def test_post_string(self):
        """
        The test of the post string.
        """
        provider = CiCdProviderGitHub()
        post_string = provider.post_string()
        self.assertIn("secrets.COGUARD_USER_NAME", post_string)

    def test_get_identifier(self):
        """
        The test to get the identifier.
        """
        provider = CiCdProviderGitHub()
        identifier = provider.get_identifier()
        self.assertEqual(identifier, "github")

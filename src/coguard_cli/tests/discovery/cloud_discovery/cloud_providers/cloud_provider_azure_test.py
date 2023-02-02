"""
Tests for the functions in the CloudProviderAzure class
"""

import unittest
import unittest.mock
from pathlib import Path
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_azure \
    import CloudProviderAzure

class TestCloudProviderAzure(unittest.TestCase):
    """
    The class for testing the Cloud provider module
    """

    def test_get_cloud_provider_name(self):
        """
        simple test checking if the name is azure
        """
        azure_provider = CloudProviderAzure()
        self.assertEqual(azure_provider.get_cloud_provider_name(), "azure")

    def test_extract_credentials_gcloud_config_path_not_existent(self):
        """
        Tests the case where the path locally to the config did not exist.
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: False
        ):
            self.assertIsNone(
                azure_provider.extract_credentials()
            )

    def test_extract_credentials_existent(self):
        """
        Tests the case where the credentials are already present
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: True
        ):
            self.assertDictEqual(
                azure_provider.extract_credentials(),
                {
                    "conf_path": Path(Path.home(), ".azure")
                }
            )

    def test_extract_iac_files_for_account_no_creds(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_azure.CloudProviderAzure.extract_credentials",
            new_callable = lambda: lambda a: None):
            self.assertIsNone(
                azure_provider.extract_iac_files_for_account(unittest.mock.Mock())
            )

    def test_extract_iac_files_for_account_docker_dao_none(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted, but docker_dao fails
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_azure.CloudProviderAzure.extract_credentials",
                new_callable = lambda: lambda a: {
                    "conf_path": Path(Path.home(), ".azure")
                }
        ), \
        unittest.mock.patch(
            'tempfile.mkdtemp',
            new_callable = lambda: lambda prefix: "/tmp/bar"
        ), \
        unittest.mock.patch(
            'coguard_cli.docker_dao.terraformer_wrapper',
            new_callable = lambda: lambda a, b, c, d, e: None
        ):
            self.assertIsNone(
                azure_provider.extract_iac_files_for_account(unittest.mock.Mock())
            )

    def test_extract_iac_files_for_account_docker_dao(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted, but docker_dao fails
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_azure.CloudProviderAzure.extract_credentials",
                new_callable = lambda: lambda a: {
                    "conf_path": Path(Path.home(), ".azure")
                }
        ), \
        unittest.mock.patch(
            'tempfile.mkdtemp',
            new_callable = lambda: lambda prefix: "/tmp/bar"
        ), \
        unittest.mock.patch(
            'coguard_cli.docker_dao.terraformer_wrapper',
            new_callable = lambda: lambda a, b, c, d, e: "foo"
        ):
            self.assertEqual(
                azure_provider.extract_iac_files_for_account(unittest.mock.Mock()),
                "/tmp/bar"
            )

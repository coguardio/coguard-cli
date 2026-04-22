"""
Tests for the functions in the CloudProviderAzure class
"""

import json
import os
import unittest
import unittest.mock
from pathlib import Path
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_azure \
    import CloudProviderAzure

MOCK_SP_CREDS = {
    "auth_mode": "service_principal",
    "ARM_CLIENT_ID": "test-client-id",
    "ARM_CLIENT_SECRET": "test-client-secret",
    "ARM_TENANT_ID": "test-tenant-id",
    "ARM_SUBSCRIPTION_ID": "test-subscription-id"
}

MOCK_CLI_CREDS = {
    "auth_mode": "cli",
    "conf_path": Path(Path.home(), ".azure")
}

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

    def test_extract_credentials_azure_config_path_not_existent(self):
        """
        Tests the case where no credentials file, no env vars,
        and the ~/.azure path does not exist.
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: False
        ), unittest.mock.patch.dict(
                os.environ, {}, clear=True
        ):
            self.assertIsNone(
                azure_provider.extract_credentials()
            )

    def test_extract_credentials_from_az_cli(self):
        """
        Tests the fallback to ~/.azure when no file or env vars are present.
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: True
        ), unittest.mock.patch.dict(
                os.environ, {}, clear=True
        ):
            self.assertDictEqual(
                azure_provider.extract_credentials(),
                MOCK_CLI_CREDS
            )

    def test_extract_credentials_from_env_vars(self):
        """
        Tests that service principal env vars take priority over ~/.azure.
        """
        azure_provider = CloudProviderAzure()
        env = {
            "ARM_CLIENT_ID": "test-client-id",
            "ARM_CLIENT_SECRET": "test-client-secret",
            "ARM_TENANT_ID": "test-tenant-id",
            "ARM_SUBSCRIPTION_ID": "test-subscription-id"
        }
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            self.assertDictEqual(
                azure_provider.extract_credentials(),
                MOCK_SP_CREDS
            )

    def test_extract_credentials_from_env_vars_incomplete(self):
        """
        Tests that incomplete env vars are ignored and falls through.
        """
        azure_provider = CloudProviderAzure()
        env = {
            "ARM_CLIENT_ID": "test-client-id",
            "ARM_TENANT_ID": "test-tenant-id"
        }
        with unittest.mock.patch.dict(os.environ, env, clear=True), \
             unittest.mock.patch(
                 'pathlib.Path.exists',
                 new_callable=lambda: lambda s: False
             ):
            self.assertIsNone(
                azure_provider.extract_credentials()
            )

    def test_extract_credentials_from_file(self):
        """
        Tests reading credentials from a JSON file.
        """
        azure_provider = CloudProviderAzure()
        file_content = json.dumps({
            "clientId": "file-client-id",
            "clientSecret": "file-client-secret",
            "tenantId": "file-tenant-id",
            "subscriptionId": "file-subscription-id"
        })
        m_open = unittest.mock.mock_open(read_data=file_content)
        with unittest.mock.patch('builtins.open', m_open):
            result = azure_provider.extract_credentials("/tmp/azure_creds.json")
            self.assertDictEqual(result, {
                "auth_mode": "service_principal",
                "ARM_CLIENT_ID": "file-client-id",
                "ARM_CLIENT_SECRET": "file-client-secret",
                "ARM_TENANT_ID": "file-tenant-id",
                "ARM_SUBSCRIPTION_ID": "file-subscription-id"
            })

    def test_extract_credentials_from_file_missing_keys(self):
        """
        Tests that a JSON file with missing keys returns None.
        """
        azure_provider = CloudProviderAzure()
        file_content = json.dumps({"clientId": "only-this"})
        m_open = unittest.mock.mock_open(read_data=file_content)
        with unittest.mock.patch('builtins.open', m_open):
            self.assertIsNone(
                azure_provider.extract_credentials("/tmp/bad_creds.json")
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
            new_callable = lambda: lambda a, b=None: None):
            self.assertIsNone(
                azure_provider.extract_iac_files_for_account(unittest.mock.Mock())
            )

    def test_extract_iac_files_for_account_cli_auth_docker_dao_none(self):
        """
        Tests that extract_iac_files_for_account returns None
        when using CLI auth but docker_dao fails.
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_azure.CloudProviderAzure.extract_credentials",
                new_callable = lambda: lambda a, b=None: dict(MOCK_CLI_CREDS)
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

    def test_extract_iac_files_for_account_cli_auth_docker_dao(self):
        """
        Tests successful extraction using CLI auth.
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_azure.CloudProviderAzure.extract_credentials",
                new_callable = lambda: lambda a, b=None: dict(MOCK_CLI_CREDS)
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

    def test_extract_iac_files_for_account_sp_auth_docker_dao(self):
        """
        Tests successful extraction using service principal auth.
        """
        azure_provider = CloudProviderAzure()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_azure.CloudProviderAzure.extract_credentials",
                new_callable = lambda: lambda a, b=None: dict(MOCK_SP_CREDS)
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

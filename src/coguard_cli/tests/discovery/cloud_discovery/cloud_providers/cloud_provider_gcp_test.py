"""
Tests for the functions in the CloudProviderGCP class
"""

import unittest
import unittest.mock
from pathlib import Path
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_gcp \
    import CloudProviderGCP

class TestCloudProviderGCP(unittest.TestCase):
    """
    The class for testing the Cloud provider module
    """

    def test_get_cloud_provider_name(self):
        """
        simple test checking if the name is gcp
        """
        gcp_provider = CloudProviderGCP()
        self.assertEqual(gcp_provider.get_cloud_provider_name(), "gcp")

    def test_get_account_id_assertion_error(self):
        """
        Simple test checking the get_account_id internal function
        """
        gcp_provider = CloudProviderGCP()
        with self.assertRaises(AssertionError):
            gcp_provider._get_account_id([])

    def test_get_account_id(self):
        """
        Simple test checking the get_account_id internal function
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
                "builtins.input",
                new_callable=lambda: lambda x: "bar"
        ):
            self.assertEqual(gcp_provider._get_account_id(["bar", "baz"]), "bar")

    def test_get_account_id_default(self):
        """
        Simple test checking the get_account_id internal function
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
                "builtins.input",
                new_callable=lambda: lambda x: " "
        ):
            self.assertEqual(gcp_provider._get_account_id(["bar", "baz"]), "bar")

    def test_extract_credentials_gcloud_config_path_not_existent(self):
        """
        Tests the case where the path locally to the config did not exist.
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: False
        ):
            self.assertIsNone(
                gcp_provider.extract_credentials()
            )

    def test_extract_credentials_no_accounts(self):
        """
        Tests the case where the credentials are already present
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.iterdir',
                new_callable=lambda: lambda s: []
        ):
            self.assertIsNone(
                gcp_provider.extract_credentials()
            )

    def test_extract_credentials_one_account_no_configs(self):
        """
        Tests the case where the credentials are already present
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.iterdir',
                new_callable=lambda: lambda s: [Path("abc.json")]
        ), \
        unittest.mock.patch(
                'pathlib.Path.is_dir',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.is_file',
                new_callable=lambda: lambda s: False
        ):
            self.assertIsNone(
                gcp_provider.extract_credentials()
            )

    def test_extract_credentials_one_account_with_configs(self):
        """
        Tests the case where the credentials are already present
        """
        gcp_provider = CloudProviderGCP()
        account_id = Path("abc.json")
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.iterdir',
                new_callable=lambda: lambda s: [account_id]
        ), \
        unittest.mock.patch(
                'pathlib.Path.is_dir',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.is_file',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.__eq__',
                new_callable=lambda: lambda s, o: True
        ), \
        unittest.mock.patch(
                'configparser.ConfigParser.read',
                new_callable=lambda: lambda s, t: {}
        ), \
        unittest.mock.patch(
                'configparser.ConfigParser.keys',
                new_callable=lambda: lambda s: ["core"]
        ), \
        unittest.mock.patch(
                'configparser.ConfigParser.__getitem__',
                new_callable=lambda: lambda s, t: {"account": account_id,
                                                   "project": "foo"}
        ), \
        unittest.mock.patch(
                'pathlib.Path.open',
                unittest.mock.mock_open(read_data="{\"foo\": 1}")
        ):
            self.assertDictEqual(
                gcp_provider.extract_credentials(),
                {"foo": 1}
            )

    def test_extract_credentials_one_account_with_configs(self):
        """
        Tests the case where the credentials are already present
        """
        gcp_provider = CloudProviderGCP()
        account_id = Path("abc.json")
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.iterdir',
                new_callable=lambda: lambda s: [account_id]
        ), \
        unittest.mock.patch(
                'pathlib.Path.is_dir',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.is_file',
                new_callable=lambda: lambda s: True
        ), \
        unittest.mock.patch(
                'pathlib.Path.__eq__',
                new_callable=lambda: lambda s, o: False
        ), \
        unittest.mock.patch(
                'configparser.ConfigParser.read',
                new_callable=lambda: lambda s, t: {}
        ), \
        unittest.mock.patch(
                'configparser.ConfigParser.keys',
                new_callable=lambda: lambda s: ["core"]
        ), \
        unittest.mock.patch(
                'configparser.ConfigParser.__getitem__',
                new_callable=lambda: lambda s, t: {"account": account_id,
                                                   "project": "foo"}
        ), \
        unittest.mock.patch(
                'pathlib.Path.open',
                unittest.mock.mock_open(read_data="{\"foo\": 1}")
        ):
            self.assertIsNone(
                gcp_provider.extract_credentials()
            )


    def test_extract_iac_files_for_account_no_creds(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_gcp.CloudProviderGCP.extract_credentials",
                new_callable = lambda: lambda a, b: None):
            self.assertIsNone(
                gcp_provider.extract_iac_files_for_account(unittest.mock.Mock())
            )

    def test_extract_iac_files_for_account_docker_dao_none(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted, but docker_dao fails
        """
        gcp_provider = CloudProviderGCP()
        auth_config = unittest.mock.Mock(
            get_username=lambda: "foo",
            get_password=lambda: "secret"
        )
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_gcp.CloudProviderGCP.extract_credentials",
                new_callable = lambda: lambda a, b: "foo"), \
            unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_gcp.CloudProviderGCP.get_all_regions",
                new_callable = lambda: lambda a: ["ca-central-1"]), \
            unittest.mock.patch(
                'tempfile.mkdtemp',
                new_callable = lambda: lambda prefix: "/tmp/bar"
            ), \
            unittest.mock.patch(
                'coguard_cli.docker_dao.terraformer_wrapper',
                new_callable = lambda: lambda a, b, c, d, e: None
            ):
            self.assertIsNone(
                gcp_provider.extract_iac_files_for_account(auth_config)
            )

    def test_extract_iac_files_for_account_docker_dao(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted, but docker_dao fails
        """
        gcp_provider = CloudProviderGCP()
        auth_config = unittest.mock.Mock(
            get_username=lambda: "foo",
            get_password=lambda: "secret"
        )
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_gcp.CloudProviderGCP.extract_credentials",
                new_callable = lambda: lambda a, b: "foo"), \
            unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_gcp.CloudProviderGCP.get_all_regions",
                new_callable = lambda: lambda a: ["ca-central-1"]), \
            unittest.mock.patch(
                'tempfile.mkdtemp',
                new_callable = lambda: lambda prefix: "/tmp/bar"
            ), \
            unittest.mock.patch(
                'coguard_cli.docker_dao.terraformer_wrapper',
                new_callable = lambda: lambda a, b, c, d, e: "foo"
            ):
            self.assertEqual(
                gcp_provider.extract_iac_files_for_account(auth_config),
                "/tmp/bar"
            )

    def test_get_all_regions_no_extraction(self):
        """
        Testing the functionality to get all regions.
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: \
                lambda cmd, check, shell, capture_output, timeout: \
                unittest.mock.Mock(
                    stdout=b"[]"
                )
        ):
            self.assertEqual(
                len(gcp_provider.get_all_regions()),
                36
            )

    def test_get_all_regions_with_extraction(self):
        """
        Testing the functionality to get all regions.
        """
        gcp_provider = CloudProviderGCP()
        with unittest.mock.patch(
                "subprocess.run",
                new_callable=lambda: \
                lambda cmd, check, shell, capture_output, timeout: \
                unittest.mock.Mock(
                    stdout=b"[{\"name\": \"foo\"}]"
                )
        ):
            self.assertEqual(
                len(gcp_provider.get_all_regions()),
                1
            )
            self.assertEqual(
                gcp_provider.get_all_regions()[0],
                "foo"
            )

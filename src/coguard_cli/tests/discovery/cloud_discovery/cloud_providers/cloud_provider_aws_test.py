"""
Tests for the functions in the CloudProviderAWS class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_aws \
    import CloudProviderAWS

class TestCloudProviderAWS(unittest.TestCase):
    """
    The class for testing the Cloud provider module
    """

    def test_get_cloud_provider_name(self):
        """
        simple test checking if the name is aws
        """
        aws_provider = CloudProviderAWS()
        self.assertEqual(aws_provider.get_cloud_provider_name(), "aws")

    def test_get_profile_assertion_error(self):
        """
        Simple test checking the get_profile internal function
        """
        aws_provider = CloudProviderAWS()
        with self.assertRaises(AssertionError):
            aws_provider._get_profile([])

    def test_get_profile(self):
        """
        Simple test checking the get_profile internal function
        """
        aws_provider = CloudProviderAWS()
        with unittest.mock.patch(
                "builtins.input",
                new_callable=lambda: lambda x: "bar"
        ):
            self.assertEqual(aws_provider._get_profile(["bar", "baz"]), "bar")

    def test_get_profile_default(self):
        """
        Simple test checking the get_profile internal function
        """
        aws_provider = CloudProviderAWS()
        with unittest.mock.patch(
                "builtins.input",
                new_callable=lambda: lambda x: " "
        ):
            self.assertEqual(aws_provider._get_profile(["bar", "baz"]), "bar")

    def test_extract_credentials_already_present(self):
        """
        Tests the case where the credentials are already present
        """
        aws_provider = CloudProviderAWS("foo", "bar")
        self.assertDictEqual(
            aws_provider.extract_credentials(),
            {
                "aws_access_key_id": "foo",
                "aws_secret_access_key": "bar"
            }
        )

    def test_extract_credentials_no_profiles_fond(self):
        """
        Tests the case where the credentials are already present
        """
        aws_provider = CloudProviderAWS()
        session = unittest.mock.Mock(
            available_profiles = [],
            get_credentials = lambda: None
        )
        with unittest.mock.patch(
                'boto3.Session',
                new_callable=lambda: lambda: session
        ):
            self.assertIsNone(
                aws_provider.extract_credentials()
            )

    def test_extract_credentials_one_profile(self):
        """
        Tests the case where the credentials are already present
        """
        aws_provider = CloudProviderAWS()
        credentials = unittest.mock.Mock(
            access_key="foo",
            secret_key="bar"
        )
        session = unittest.mock.Mock(
            available_profiles = ['default'],
            get_credentials = lambda: credentials

        )
        with unittest.mock.patch(
                'boto3.Session',
                new_callable=lambda: lambda: session
        ):
            self.assertDictEqual(
                aws_provider.extract_credentials(),
                {
                    "aws_access_key_id": "foo",
                    "aws_secret_access_key": "bar"
                }
            )

    def test_extract_credentials_multiple_profiles(self):
        """
        Tests the case where the credentials are already present
        """
        aws_provider = CloudProviderAWS()
        credentials = unittest.mock.Mock(
            access_key="foo",
            secret_key="bar"
        )
        session = unittest.mock.Mock(
            available_profiles = ['default', 'mock'],
            get_credentials = lambda: credentials

        )
        def session_function(profile_name = "foo"):
            return session
        with unittest.mock.patch(
                'boto3.Session',
                new_callable=lambda: session_function
        ), \
        unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_aws.CloudProviderAWS._get_profile",
            new_callable = lambda: lambda a, l: l[0]
        ):
            self.assertDictEqual(
                aws_provider.extract_credentials(),
                {
                    "aws_access_key_id": "foo",
                    "aws_secret_access_key": "bar"
                }
            )

    def test_extract_iac_files_for_account_no_creds(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted
        """
        aws_provider = CloudProviderAWS()
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_aws.CloudProviderAWS.extract_credentials",
            new_callable = lambda: lambda a: None):
            self.assertIsNone(
                aws_provider.extract_iac_files_for_account(unittest.mock.Mock())
            )

    def test_extract_iac_files_for_account_docker_dao_none(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted, but docker_dao fails
        """
        aws_provider = CloudProviderAWS()
        auth_config = unittest.mock.Mock(
            get_username=lambda: "foo",
            get_password=lambda: "secret"
        )
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_aws.CloudProviderAWS.extract_credentials",
            new_callable = lambda: lambda a: "foo"), \
            unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_aws.CloudProviderAWS.get_all_regions",
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
                aws_provider.extract_iac_files_for_account(auth_config)
            )

    def test_extract_iac_files_for_account_docker_dao(self):
        """
        Simple function to test that extract_iac_files_for_account
        returns None if no credentials can be extracted, but docker_dao fails
        """
        aws_provider = CloudProviderAWS()
        auth_config = unittest.mock.Mock(
            get_username=lambda: "foo",
            get_password=lambda: "secret"
        )
        with unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_aws.CloudProviderAWS.extract_credentials",
            new_callable = lambda: lambda a: "foo"), \
            unittest.mock.patch(
            "coguard_cli.discovery.cloud_discovery.cloud_providers." + \
            "cloud_provider_aws.CloudProviderAWS.get_all_regions",
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
                aws_provider.extract_iac_files_for_account(auth_config),
                "/tmp/bar"
            )

    def test_get_all_regions(self):
        """
        Testing the functionality to get all regions.
        """
        aws_provider = CloudProviderAWS()
        mock_client = unittest.mock.Mock(
            describe_regions = lambda: {"Regions": [{"RegionName": "ca-central-1"}]}
        )
        with unittest.mock.patch(
                'boto3.client',
                new_callable = lambda: lambda resource: mock_client
        ):
            self.assertListEqual(
                aws_provider.get_all_regions(),
                ["ca-central-1"]
            )

    def test_get_all_regions_no_extraction(self):
        """
        Testing the functionality to get all regions.
        """
        aws_provider = CloudProviderAWS()
        mock_client = unittest.mock.Mock(
            describe_regions = lambda: {"Regions": [{"RegionName": "ca-central-1"}]}
        )
        def new_callable(resource):
            raise ValueError("foo")
        with unittest.mock.patch(
                'boto3.client',
                new_callable = lambda: new_callable
        ):
            self.assertEqual(
                len(aws_provider.get_all_regions()),
                27
            )

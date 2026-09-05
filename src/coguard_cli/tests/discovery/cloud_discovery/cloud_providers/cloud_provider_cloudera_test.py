"""
Tests for the functions in the CloudProviderCloudera class
"""

import unittest
import unittest.mock
from coguard_cli.auth.auth_config import CoGuardCliConfig
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_cloudera \
    import CloudProviderCloudera
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApiError

class TestCloudProviderCloudera(unittest.TestCase):
    """
    The class for testing the Cloudera cloud provider module
    """

    def test_get_cloud_provider_name(self):
        """
        Simple test checking if the name is cloudera
        """
        self.assertEqual(
            CloudProviderCloudera().get_cloud_provider_name(),
            "cloudera"
        )

    def test_set_options(self):
        """
        The options passed after the factory instantiation are picked up.
        """
        provider = CloudProviderCloudera()
        provider.set_options({"url": "https://cm.example.com"})
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch("sys.stdin.isatty",
                                     new_callable=lambda: lambda: False):
                # The user is still missing, hence None; but the url was stored.
                self.assertIsNone(provider.extract_credentials())
        provider.set_options(None)
        # pylint: disable=protected-access
        self.assertEqual(provider._options, {})

    def test_extract_credentials_from_options(self):
        """
        The command line options are used as the primary source.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin",
            "password": "secret"
        })
        with unittest.mock.patch("os.environ", {}):
            credentials = provider.extract_credentials()
        self.assertEqual(credentials["url"], "https://cm.example.com")
        self.assertEqual(credentials["username"], "admin")
        self.assertEqual(credentials["password"], "secret")
        self.assertTrue(credentials["verify_tls"])

    def test_extract_credentials_from_environment(self):
        """
        The environment variables are used if nothing else is provided.
        """
        provider = CloudProviderCloudera()
        with unittest.mock.patch("os.environ", {
                "CLOUDERA_MANAGER_URL": "https://cm.example.com",
                "CLOUDERA_MANAGER_USER": "admin",
                "CLOUDERA_MANAGER_PASSWORD": "secret",
                "CLOUDERA_CLUSTER": "ozone-base-cluster"
        }):
            credentials = provider.extract_credentials()
        self.assertEqual(credentials["url"], "https://cm.example.com")
        self.assertEqual(credentials["cluster"], "ozone-base-cluster")

    def test_extract_credentials_options_take_precedence(self):
        """
        Command line options win over the credentials file and the environment.
        """
        provider = CloudProviderCloudera({"username": "from-options"})
        with unittest.mock.patch(
                "coguard_cli.discovery.cloud_discovery.cloud_providers."
                "cloud_provider_cloudera.CloudProviderCloudera."
                "_load_credentials_file",
                new_callable=lambda: staticmethod(lambda credentials_file: {
                    "username": "from-file",
                    "password": "from-file"
                })
        ):
            with unittest.mock.patch("os.environ", {
                    "CLOUDERA_MANAGER_URL": "https://cm.example.com",
                    "CLOUDERA_MANAGER_USER": "from-environment",
                    "CLOUDERA_MANAGER_PASSWORD": "from-environment"
            }):
                credentials = provider.extract_credentials("creds.json")
        self.assertEqual(credentials["username"], "from-options")
        # Not provided as an option, hence taken from the file.
        self.assertEqual(credentials["password"], "from-file")
        # Neither option nor file, hence taken from the environment.
        self.assertEqual(credentials["url"], "https://cm.example.com")

    def test_extract_credentials_missing_url(self):
        """
        A missing url results in None.
        """
        provider = CloudProviderCloudera({"username": "admin", "password": "s"})
        with unittest.mock.patch("os.environ", {}):
            self.assertIsNone(provider.extract_credentials())

    def test_extract_credentials_missing_username(self):
        """
        A missing user results in None.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "password": "s"
        })
        with unittest.mock.patch("os.environ", {}):
            self.assertIsNone(provider.extract_credentials())

    def test_extract_credentials_missing_password_non_interactive(self):
        """
        Without a terminal, a missing password cannot be prompted for.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin"
        })
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch("sys.stdin.isatty",
                                     new_callable=lambda: lambda: False):
                self.assertIsNone(provider.extract_credentials())

    def test_extract_credentials_password_prompt(self):
        """
        With a terminal, a missing password is prompted for.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin"
        })
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch("sys.stdin.isatty",
                                     new_callable=lambda: lambda: True):
                with unittest.mock.patch(
                        "getpass.getpass",
                        new_callable=lambda: lambda prompt: "prompted"
                ):
                    credentials = provider.extract_credentials()
        self.assertEqual(credentials["password"], "prompted")

    def test_extract_credentials_empty_password_prompt(self):
        """
        An empty answer to the password prompt results in None.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin"
        })
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch("sys.stdin.isatty",
                                     new_callable=lambda: lambda: True):
                with unittest.mock.patch(
                        "getpass.getpass",
                        new_callable=lambda: lambda prompt: ""
                ):
                    self.assertIsNone(provider.extract_credentials())

    def test_extract_credentials_verify_tls_string_coercion(self):
        """
        A string valued verify_tls setting is interpreted as a boolean.
        """
        base = {
            "url": "https://cm.example.com",
            "username": "admin",
            "password": "secret"
        }
        for value, expected in [
                ("false", False),
                ("FALSE", False),
                ("0", False),
                ("no", False),
                ("off", False),
                ("true", True),
                ("1", True)
        ]:
            provider = CloudProviderCloudera({**base, "verify_tls": value})
            with unittest.mock.patch("os.environ", {}):
                credentials = provider.extract_credentials()
            self.assertEqual(credentials["verify_tls"], expected, msg=value)

    def test_extract_credentials_verify_tls_false_option(self):
        """
        The `--cloudera-manager-no-verify-tls` flag switches verification off.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin",
            "password": "secret",
            "verify_tls": False
        })
        with unittest.mock.patch("os.environ", {}):
            self.assertFalse(provider.extract_credentials()["verify_tls"])

    def test_load_credentials_file_json(self):
        """
        A JSON credentials file is parsed.
        """
        with unittest.mock.patch(
                "builtins.open",
                unittest.mock.mock_open(read_data='{"username": "admin"}')
        ):
            # pylint: disable=protected-access
            self.assertEqual(
                CloudProviderCloudera._load_credentials_file("creds.json"),
                {"username": "admin"}
            )

    def test_load_credentials_file_yaml(self):
        """
        A YAML credentials file is parsed as a fallback.
        """
        with unittest.mock.patch(
                "builtins.open",
                unittest.mock.mock_open(read_data='username: admin\npassword: s')
        ):
            # pylint: disable=protected-access
            self.assertEqual(
                CloudProviderCloudera._load_credentials_file("creds.yaml"),
                {"username": "admin", "password": "s"}
            )

    def test_load_credentials_file_unreadable(self):
        """
        An unreadable credentials file results in an empty dictionary.
        """
        with unittest.mock.patch(
                "builtins.open",
                side_effect=OSError("no such file")
        ):
            # pylint: disable=protected-access
            self.assertEqual(
                CloudProviderCloudera._load_credentials_file("creds.json"),
                {}
            )

    def test_load_credentials_file_unparseable(self):
        """
        Content which is neither JSON nor YAML results in an empty dictionary.
        """
        with unittest.mock.patch(
                "builtins.open",
                unittest.mock.mock_open(read_data='\tfoo: [')
        ):
            # pylint: disable=protected-access
            self.assertEqual(
                CloudProviderCloudera._load_credentials_file("creds.yaml"),
                {}
            )

    def test_load_credentials_file_not_a_mapping(self):
        """
        A YAML document which is not a mapping results in an empty dictionary.
        """
        with unittest.mock.patch(
                "builtins.open",
                unittest.mock.mock_open(read_data='- one\n- two')
        ):
            # pylint: disable=protected-access
            self.assertEqual(
                CloudProviderCloudera._load_credentials_file("creds.yaml"),
                {}
            )

    def test_extract_iac_files_for_account(self):
        """
        Cloudera does not have an Infrastructure as Code representation.
        """
        self.assertIsNone(
            CloudProviderCloudera().extract_iac_files_for_account(
                CoGuardCliConfig("user", None, None, None)
            )
        )

    def test_extract_cluster_representation(self):
        """
        The happy path delegates to the Cloudera discovery module.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin",
            "password": "secret",
            "cluster": "ozone-base-cluster"
        })
        api = unittest.mock.MagicMock()
        api.check_connection.return_value = True
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch(
                    "coguard_cli.discovery.cloud_discovery.cloud_providers."
                    "cloud_provider_cloudera.ClouderaManagerApi",
                    new_callable=lambda: lambda **kwargs: api
            ):
                with unittest.mock.patch(
                        "coguard_cli.discovery.cloud_discovery.cloud_providers."
                        "cloud_provider_cloudera."
                        "extract_cloudera_cluster_representation",
                        new_callable=lambda: lambda api, customer_id, cluster:
                        ("/tmp/folder", {"name": cluster,
                                         "customerId": customer_id})
                ):
                    result = provider.extract_cluster_representation(
                        CoGuardCliConfig("user", None, None, None)
                    )
        self.assertEqual(
            result,
            ("/tmp/folder", {"name": "ozone-base-cluster", "customerId": "user"})
        )

    def test_extract_cluster_representation_customer_id_override(self):
        """
        An explicitly provided customer id is used over the configured user.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin",
            "password": "secret"
        })
        api = unittest.mock.MagicMock()
        api.check_connection.return_value = True
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch(
                    "coguard_cli.discovery.cloud_discovery.cloud_providers."
                    "cloud_provider_cloudera.ClouderaManagerApi",
                    new_callable=lambda: lambda **kwargs: api
            ):
                with unittest.mock.patch(
                        "coguard_cli.discovery.cloud_discovery.cloud_providers."
                        "cloud_provider_cloudera."
                        "extract_cloudera_cluster_representation",
                        new_callable=lambda: lambda api, customer_id, cluster:
                        ("/tmp/folder", {"customerId": customer_id})
                ):
                    result = provider.extract_cluster_representation(
                        CoGuardCliConfig("user", None, None, None),
                        None,
                        "organization"
                    )
        self.assertEqual(result[1]["customerId"], "organization")

    def test_extract_cluster_representation_no_credentials(self):
        """
        Without credentials, None is returned.
        """
        provider = CloudProviderCloudera()
        with unittest.mock.patch("os.environ", {}):
            self.assertIsNone(
                provider.extract_cluster_representation(
                    CoGuardCliConfig("user", None, None, None)
                )
            )

    def test_extract_cluster_representation_invalid_url(self):
        """
        An unusable url is reported and results in None.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin",
            "password": "secret"
        })
        def _raise(**kwargs):
            raise ClouderaManagerApiError("bad url")
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch(
                    "coguard_cli.discovery.cloud_discovery.cloud_providers."
                    "cloud_provider_cloudera.ClouderaManagerApi",
                    new_callable=lambda: _raise
            ):
                self.assertIsNone(
                    provider.extract_cluster_representation(
                        CoGuardCliConfig("user", None, None, None)
                    )
                )

    def test_extract_cluster_representation_connection_failure(self):
        """
        A failing connection check results in None.
        """
        provider = CloudProviderCloudera({
            "url": "https://cm.example.com",
            "username": "admin",
            "password": "secret"
        })
        api = unittest.mock.MagicMock()
        api.check_connection.return_value = False
        with unittest.mock.patch("os.environ", {}):
            with unittest.mock.patch(
                    "coguard_cli.discovery.cloud_discovery.cloud_providers."
                    "cloud_provider_cloudera.ClouderaManagerApi",
                    new_callable=lambda: lambda **kwargs: api
            ):
                self.assertIsNone(
                    provider.extract_cluster_representation(
                        CoGuardCliConfig("user", None, None, None)
                    )
                )

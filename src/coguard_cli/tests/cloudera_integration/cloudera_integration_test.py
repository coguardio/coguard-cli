"""
Tests for the shared helpers of the Cloudera integration entry points.
"""

import argparse
import unittest
import unittest.mock

from coguard_cli.cloudera_integration import add_cloudera_manager_arguments, \
    cloudera_manager_options, connect, resolve_credentials
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApiError


def parse(arguments):
    """
    A helper to parse a command line with the shared Cloudera Manager
    arguments.
    """
    parser = argparse.ArgumentParser()
    add_cloudera_manager_arguments(parser)
    return parser.parse_args(arguments)


class TestClouderaIntegration(unittest.TestCase):
    """
    The class for testing the shared helpers of the Cloudera integration.
    """

    def test_cloudera_manager_options_only_contains_provided_values(self):
        """
        Values which were not provided are left out, so that the provider can
        fall back to a credentials file or the environment.
        """
        self.assertEqual(
            cloudera_manager_options(parse([
                "--cloudera-manager-url", "https://cm.example.com"
            ])),
            {"url": "https://cm.example.com"}
        )

    def test_cloudera_manager_options_complete(self):
        """
        Every connection parameter is translated to the key the provider uses.
        """
        self.assertEqual(
            cloudera_manager_options(parse([
                "--cloudera-manager-url", "https://cm.example.com",
                "--cloudera-manager-user", "coguard",
                "--cloudera-manager-ca-cert", "/etc/ssl/cm.pem",
                "--cloudera-cluster", "ozone-base-cluster"
            ])),
            {
                "url": "https://cm.example.com",
                "username": "coguard",
                "ca_cert": "/etc/ssl/cm.pem",
                "cluster": "ozone-base-cluster"
            }
        )

    def test_tls_verification_cannot_be_switched_off(self):
        """
        There is no option to skip the verification of the certificate of
        Cloudera Manager.
        """
        with unittest.mock.patch('sys.stderr'), \
             self.assertRaises(SystemExit):
            parse(["--cloudera-manager-url", "https://cm.example.com",
                   "--cloudera-manager-no-verify-tls"])

    def test_logging_level_choices(self):
        """
        The logging level is one of those `coguard` accepts, so that a level
        which `coguard-cloudera-check` hands on to the scan is never rejected
        only once the scan runs.
        """
        parser = argparse.ArgumentParser()
        add_cloudera_manager_arguments(parser)
        self.assertEqual(parser.parse_args([]).logging_level, "INFO")
        self.assertEqual(
            parser.parse_args(["--logging-level", "DEBUG"]).logging_level,
            "DEBUG"
        )
        with unittest.mock.patch('sys.stderr'), \
             self.assertRaises(SystemExit):
            parser.parse_args(["--logging-level", "NONSENSE"])

    def test_resolve_credentials(self):
        """
        The credentials are resolved by the Cloudera provider of the CLI, with
        the options of this command line and the credentials file it was given.
        """
        provider = unittest.mock.MagicMock()
        provider.extract_credentials.return_value = {"url": "https://cm"}
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.CloudProviderCloudera',
                new_callable=lambda: unittest.mock.MagicMock(
                    return_value=provider
                )
        ) as provider_class:
            self.assertEqual(
                resolve_credentials(parse([
                    "--cloudera-manager-url", "https://cm",
                    "--credentials-file", "/etc/coguard/cloudera.yaml"
                ])),
                {"url": "https://cm"}
            )
            provider_class.assert_called_once_with({"url": "https://cm"})
            provider.extract_credentials.assert_called_once_with(
                "/etc/coguard/cloudera.yaml"
            )

    def test_connect(self):
        """
        A reachable Cloudera Manager results in a client.
        """
        api = unittest.mock.MagicMock()
        api.check_connection.return_value = True
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.ClouderaManagerApi',
                new_callable=lambda: unittest.mock.MagicMock(return_value=api)
        ):
            self.assertEqual(
                connect({
                    "url": "https://cm",
                    "username": "coguard",
                    "password": "secret"
                }),
                api
            )

    def test_connect_unreachable(self):
        """
        A Cloudera Manager which does not answer results in `None`.
        """
        api = unittest.mock.MagicMock()
        api.check_connection.return_value = False
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.ClouderaManagerApi',
                new_callable=lambda: unittest.mock.MagicMock(return_value=api)
        ):
            self.assertIsNone(connect({
                "url": "https://cm",
                "username": "coguard",
                "password": "secret"
            }))

    def test_connect_unusable_url(self):
        """
        A url which cannot describe a Cloudera Manager results in `None`.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.ClouderaManagerApi',
                side_effect=ClouderaManagerApiError("no host")
        ):
            self.assertIsNone(connect({
                "url": "not a url",
                "username": "coguard",
                "password": "secret"
            }))

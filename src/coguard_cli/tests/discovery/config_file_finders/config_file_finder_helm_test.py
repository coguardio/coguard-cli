"""
Tests for the functions in the ConfigFileFinderHelm class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_helm \
    import ConfigFileFinderHelm

class TestConfigFileFinderHelm(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderHelm module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderHelm().get_service_name(), "kubernetes")

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable=lambda: lambda location: False):
            config_file_finder_helm = ConfigFileFinderHelm()
            self.assertIsNone(
                config_file_finder_helm.check_for_config_files_in_standard_location(
                "foo"
            ))

    def test_check_for_config_files_in_standard_location_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.lexists",
                new_callable=lambda: lambda location: True), \
             unittest.mock.patch(
                 ("coguard_cli.discovery.config_file_finders.config_file_finder"
                  "_helm.ConfigFileFinderHelm._create_temp_"
                  "location_and_manifest_entry"),
                 new_callable=lambda: lambda a, b, c, d, e, f: ({"foo": "bar"}, "/etc/bar")
             ):
            config_file_finder_helm = ConfigFileFinderHelm()
            self.assertIsNone(
                config_file_finder_helm.check_for_config_files_in_standard_location(
                    "foo"
                )
            )

    def test_check_for_config_files_filesystem_search_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertListEqual(result, [])

    def test_find_charts_files_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm._find_charts_files(
                "foo"
            )
            self.assertListEqual(result, [])

    def test_find_charts_files_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["Chart.yaml"])]), \
            unittest.mock.patch(
                ("coguard_cli.discovery.config_file_finders."
                 "does_config_yaml_contain_required_keys"),
                new_callable=lambda: lambda a, b: True):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm._find_charts_files(
                "foo"
            )
            self.assertListEqual(result, ["etc/Chart.yaml"])

    def test_check_for_config_files_filesystem_search_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                ("coguard_cli.discovery.config_file_finders.config_file_"
                 "finder_helm.ConfigFileFinderHelm._find_charts_files"),
                new_callable=lambda: lambda a, b: ["foo"]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.config_file_finder"
                     "_helm.ConfigFileFinderHelm._create_temp_"
                     "location_and_manifest_entry"),
                    new_callable=lambda: lambda a, b, c: ({"foo": "bar"}, "/etc/bar")
                ):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], {"foo": "bar"})
            self.assertEqual(result[0][1], "/etc/bar")

    def test_check_call_command_in_container(self):
        """
        The function to test the attempted extraction of the my.cnf
        location from call commands.
        """
        config_file_finder_helm = ConfigFileFinderHelm()
        result = config_file_finder_helm.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "Cmd": [
                        "/bin/sh",
                        "-c",
                        "helm-server /etc/helm.conf"
                    ],
                    "WorkingDir": "",
                    "Entrypoint": [
                        "/docker-entrypoint.sh"
                    ],
                }
            }
        )
        self.assertListEqual(result, [])

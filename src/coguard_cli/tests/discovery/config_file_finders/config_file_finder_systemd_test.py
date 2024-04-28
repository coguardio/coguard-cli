"""
Tests for the functions in the ConfigFileFinderSystemd class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_systemd \
    import ConfigFileFinderSystemd

class TestConfigFileFinderSystemd(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderSystemd module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderSystemd().get_service_name(), "systemd")

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable=lambda: lambda location: False):
            config_file_finder_systemd = ConfigFileFinderSystemd()
            self.assertIsNone(
                config_file_finder_systemd.check_for_config_files_in_standard_location(
                "foo"
            ))

    def test_check_for_config_files_in_standard_location_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.lexists",
                new_callable=lambda: lambda location: True):
            config_file_finder_systemd = ConfigFileFinderSystemd()
            self.assertIsNone(
                config_file_finder_systemd.check_for_config_files_in_standard_location(
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
            config_file_finder_systemd = ConfigFileFinderSystemd()
            result = config_file_finder_systemd.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertListEqual(result, [])

    def test_check_for_config_files_filesystem_search_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["main.yml"])]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.create_grouped_temp_"
                     "locations_and_manifest_entries"),
                    new_callable=lambda: lambda a, b, c, d, e: [({"foo": "bar"}, "/etc/bar")]
                ):
            config_file_finder_systemd = ConfigFileFinderSystemd()
            result = config_file_finder_systemd.check_for_config_files_filesystem_search(
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
        config_file_finder_systemd = ConfigFileFinderSystemd()
        result = config_file_finder_systemd.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "Cmd": [
                        "/bin/sh",
                        "-c",
                        "systemd-server /etc/systemd.conf"
                    ],
                    "WorkingDir": "",
                    "Entrypoint": [
                        "/docker-entrypoint.sh"
                    ],
                }
            }
        )
        self.assertListEqual(result, [])

    def test_is_cluster_service(self):
        """
        Testing the function to see if we can parse a tf file.
        """
        config_file_finder_systemd = ConfigFileFinderSystemd()
        self.assertFalse(config_file_finder_systemd.is_cluster_service())

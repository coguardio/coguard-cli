"""
Tests for the functions in the ConfigFileFinderOpen_Afs class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_open_afs \
    import ConfigFileFinderOpenAfs

class TestConfigFileFinderOpenAfs(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderOpenAfs module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderOpenAfs().get_service_name(), "open_afs")

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable=lambda: lambda location: False):
            config_file_finder_open_afs = ConfigFileFinderOpenAfs()
            self.assertIsNone(
                config_file_finder_open_afs.check_for_config_files_in_standard_location(
                "foo"
            ))

    def test_check_for_config_files_filesystem_search_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            config_file_finder_open_afs = ConfigFileFinderOpenAfs()
            result = config_file_finder_open_afs.check_for_config_files_filesystem_search(
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
                new_callable=lambda: lambda location: [("etc", [], ["NoAuth"])]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.create_temp_"
                     "location_and_manifest_entry_same_service"),
                    new_callable=lambda: lambda a, b, c: ({"foo": "bar"}, "/etc/bar")
                ):
            config_file_finder_open_afs = ConfigFileFinderOpenAfs()
            result = config_file_finder_open_afs.check_for_config_files_filesystem_search(
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
        config_file_finder_open_afs = ConfigFileFinderOpenAfs()
        result = config_file_finder_open_afs.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "Cmd": [
                        "/bin/sh",
                        "-c",
                        "open_afs-server /etc/open_afs.conf"
                    ],
                    "WorkingDir": "",
                    "Entrypoint": [
                        "/docker-entrypoint.sh"
                    ],
                }
            }
        )
        self.assertListEqual(result, [])

"""
Tests for the functions in the ConfigFileFinderDockerDaemon class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_docker_daemon \
    import ConfigFileFinderDockerDaemon

class TestConfigFileFinderDockerDaemon(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderDockerDaemon module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderDockerDaemon().get_service_name(), "docker_daemon")

    def test_check_for_config_files_in_standard_location(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.lexists",
                new_callable=lambda: lambda location: True):
            config_file_finder_docker_daemon = ConfigFileFinderDockerDaemon()
            self.assertIsNone(
                config_file_finder_docker_daemon.check_for_config_files_in_standard_location(
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
            config_file_finder_docker_daemon = ConfigFileFinderDockerDaemon()
            result = config_file_finder_docker_daemon.check_for_config_files_filesystem_search(
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
                new_callable=lambda: lambda location: [("etc", [], ["daemon.json"])]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.create_temp_"
                     "location_and_manifest_entry"),
                    new_callable=lambda: lambda a, b, c, d, e, f: [({"foo": "bar"}, "/etc/bar")]
                ):
            config_file_finder_docker_daemon = ConfigFileFinderDockerDaemon()
            result = config_file_finder_docker_daemon.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0][0], {"foo": "bar"})
            self.assertEqual(result[0][0][1], "/etc/bar")

    def test_check_call_command_in_container(self):
        """
        The function to test the attempted extraction of the my.cnf
        location from call commands.
        """
        config_file_finder_docker_daemon = ConfigFileFinderDockerDaemon()
        result = config_file_finder_docker_daemon.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "Cmd": [
                        "/bin/sh",
                        "-c",
                        "docker_daemon-server /etc/docker_daemon.conf"
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
        config_file_finder_docker_daemon = ConfigFileFinderDockerDaemon()
        self.assertFalse(config_file_finder_docker_daemon.is_cluster_service())

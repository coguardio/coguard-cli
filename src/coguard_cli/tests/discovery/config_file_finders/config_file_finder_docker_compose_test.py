"""
Tests for the functions in the ConfigFileFinderDocker_Compose class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_docker_compose \
    import ConfigFileFinderDockerCompose

class TestConfigFileFinderDockerCompose(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderDocker_Compose module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderDockerCompose().get_service_name(), "docker_compose")

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable=lambda: lambda location: False):
            config_file_finder_docker_compose = ConfigFileFinderDockerCompose()
            self.assertIsNone(
                config_file_finder_docker_compose.check_for_config_files_in_standard_location(
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
                 ("coguard_cli.discovery.config_file_finders.create_temp_"
                  "location_and_manifest_entry"),
                 new_callable=lambda: lambda a, b, c, d, e, f: ({"foo": "bar"}, "/etc/bar")
             ):
            config_file_finder_docker_compose = ConfigFileFinderDockerCompose()
            result = config_file_finder_docker_compose.check_for_config_files_in_standard_location(
                "foo"
            )
            self.assertIsNotNone(result)
            self.assertEqual(result[0], {"foo": "bar"})
            self.assertEqual(result[1], "/etc/bar")

    def test_check_for_config_files_filesystem_search_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            config_file_finder_docker_compose = ConfigFileFinderDockerCompose()
            result = config_file_finder_docker_compose.check_for_config_files_filesystem_search(
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
                new_callable=lambda: lambda location: [("etc", [], ["docker-compose.yaml"])]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.create_temp_"
                     "location_and_manifest_entry"),
                    new_callable=lambda: lambda a, b, c, d, e, f: ({"foo": "bar"}, "/etc/bar")
                ):
            config_file_finder_docker_compose = ConfigFileFinderDockerCompose()
            result = config_file_finder_docker_compose.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], {"foo": "bar"})
            self.assertEqual(result[0][1], "/etc/bar")

    def test_check_for_config_files_filesystem_search_existing_alt(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["docker-compose.dev.yaml"])]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.create_temp_"
                     "location_and_manifest_entry"),
                    new_callable=lambda: lambda a, b, c, d, e, f: ({"foo": "bar"}, "/etc/bar")
                ):
            config_file_finder_docker_compose = ConfigFileFinderDockerCompose()
            result = config_file_finder_docker_compose.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], {"foo": "bar"})
            self.assertEqual(result[0][1], "/etc/bar")

    def test_check_for_config_files_filesystem_search_existing_alt2(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["docker-compose.dev.yml"])]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.create_temp_"
                     "location_and_manifest_entry"),
                    new_callable=lambda: lambda a, b, c, d, e, f: ({"foo": "bar"}, "/etc/bar")
                ):
            config_file_finder_docker_compose = ConfigFileFinderDockerCompose()
            result = config_file_finder_docker_compose.check_for_config_files_filesystem_search(
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
        config_file_finder_docker_compose = ConfigFileFinderDockerCompose()
        result = config_file_finder_docker_compose.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "Cmd": [
                        "/bin/sh",
                        "-c",
                        "docker_compose-server /etc/docker_compose.conf"
                    ],
                    "WorkingDir": "",
                    "Entrypoint": [
                        "/docker-entrypoint.sh"
                    ],
                }
            }
        )
        self.assertListEqual(result, [])

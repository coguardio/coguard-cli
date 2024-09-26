"""
Tests for the functions in the ConfigFileFinderAnsible class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_ansible \
    import ConfigFileFinderAnsible

class TestConfigFileFinderAnsible(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderAnsible module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderAnsible().get_service_name(), "ansible")

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable=lambda: lambda location: False):
            config_file_finder_ansible = ConfigFileFinderAnsible()
            self.assertIsNone(
                config_file_finder_ansible.check_for_config_files_in_standard_location(
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
            config_file_finder_ansible = ConfigFileFinderAnsible()
            self.assertIsNone(
                config_file_finder_ansible.check_for_config_files_in_standard_location(
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
            config_file_finder_ansible = ConfigFileFinderAnsible()
            result = config_file_finder_ansible.check_for_config_files_filesystem_search(
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
                ), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders."
                     "does_config_yaml_contain_required_keys"),
                    new_callable=lambda: lambda a, b: True
                ), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders."
                     "config_file_finder_ansible.ConfigFileFinderAnsible.is_valid_ansible_file"),
                    new_callable=lambda: lambda a, b: True
                ):
            config_file_finder_ansible = ConfigFileFinderAnsible()
            result = config_file_finder_ansible.check_for_config_files_filesystem_search(
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
        config_file_finder_ansible = ConfigFileFinderAnsible()
        result = config_file_finder_ansible.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "Cmd": [
                        "/bin/sh",
                        "-c",
                        "ansible-server /etc/ansible.conf"
                    ],
                    "WorkingDir": "",
                    "Entrypoint": [
                        "/docker-entrypoint.sh"
                    ],
                }
            }
        )
        self.assertListEqual(result, [])

    def test_is_valid_ansible_file(self):
        """
        Testing the function to see if we can parse a tf file.
        """
        with unittest.mock.patch(
                'os.path.abspath',
                new_callable=lambda: lambda location: "/foo/bar/baz"):
            config_file_finder_ansible = ConfigFileFinderAnsible()
            self.assertFalse(config_file_finder_ansible.is_valid_ansible_file(
                "foo.txt"
            ))

    def test_is_valid_ansible_file_with_subpath_match(self):
        """
        Testing the function to see if we can parse a tf file.
        """
        with unittest.mock.patch(
                'os.path.abspath',
                new_callable=lambda: lambda location: "/foo/bar/tasks/main.yml"), \
                unittest.mock.patch(
                    ('coguard_cli.discovery.config_file_finders.'
                     'does_config_yaml_contain_required_keys'),
                    new_callable=lambda: lambda location, lst: True):
            config_file_finder_ansible = ConfigFileFinderAnsible()
            self.assertTrue(config_file_finder_ansible.is_valid_ansible_file(
                "foo.txt"
            ))

    def test_is_valid_ansible_file_actual_playbook(self):
        """
        Testing an actual playbook.
        """
        config_file_finder_ansible = ConfigFileFinderAnsible()
        self.assertTrue(config_file_finder_ansible.is_valid_ansible_file(
            "./coguard_cli/tests/discovery/config_file_finders/resources/playbook.yaml"
        ))

    def test_is_invalid_ansible_file_actual_playbook(self):
        """
        Testing an actual playbook.
        """
        config_file_finder_ansible = ConfigFileFinderAnsible()
        self.assertFalse(config_file_finder_ansible.is_valid_ansible_file(
            "./coguard_cli/tests/discovery/config_file_finders/resources/wannabe_playbook.yaml"
        ))

    def test_is_cluster_service(self):
        """
        Testing the function to see if we can parse a tf file.
        """
        config_file_finder_ansible = ConfigFileFinderAnsible()
        self.assertTrue(config_file_finder_ansible.is_cluster_service())

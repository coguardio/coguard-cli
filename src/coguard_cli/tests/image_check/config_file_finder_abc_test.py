"""
Tests for the functions in the ConfigFileFinder class
"""

import unittest
import unittest.mock
from typing import Dict
from coguard_cli.image_check.config_file_finder_abc import ConfigFileFinder

class TestDockerDao(unittest.TestCase):
    """
    The class for testing the ConfigFileFinder module.
    """

    class ConfigFileFinderMockery(ConfigFileFinder):
        """
        An implementation of the base class to be used in tests.
        """

        def check_for_config_files_in_standard_location(
                self,
                path_to_file_system: str):
            if path_to_file_system != "standard_location":
                return None
            return (
                {
                    "foo": "barstandard"
                },
                "/bla/bli/blupp"
            )

        def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str):
            if path_to_file_system != "filesystem_search":
                return []
            return [(
                {
                    "foo": "barfilesystem_search"
                },
                "/bla/bli/blupp"
            )]

        def check_call_command_in_container(
                self,
                path_to_file_system: str,
                docker_config: Dict):
            if path_to_file_system != "container_command":
                return []
            return [(
                {
                    "foo": "barcontainer_command"
                },
                "/bla/bli/blupp"
            )]

        def get_service_name(self):
            return "fooService"

    def test_get_service_name(self):
        """
        Tests the basic initialization of the class.
        """
        mock_class = self.ConfigFileFinderMockery()
        self.assertEqual(mock_class.get_service_name(), "fooService")

    def test_find_config_files_fail_everywhere(self):
        """
        Tests the finding of the configuration files failing everywhere.
        """
        mock_class = self.ConfigFileFinderMockery()
        self.assertListEqual(mock_class.find_configuration_files("", {}), [])

    def test_find_config_files_standard(self):
        """
        Tests the finding of the configuration files using the standard method.
        """
        mock_class = self.ConfigFileFinderMockery()
        res = mock_class.find_configuration_files("standard_location", {})
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0]["foo"], "barstandard")

    def test_find_config_files_file_system_search(self):
        """
        Tests the finding of the configuration files using the file system
        search method.
        """
        mock_class = self.ConfigFileFinderMockery()
        res = mock_class.find_configuration_files("filesystem_search", {})
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0]["foo"], "barfilesystem_search")

    def test_find_config_files_executable_search(self):
        """
        Tests the finding of the configuration files using the file system
        search method.
        """
        mock_class = self.ConfigFileFinderMockery()
        res = mock_class.find_configuration_files("container_command", {})
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0]["foo"], "barcontainer_command")

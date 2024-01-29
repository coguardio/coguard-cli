"""
This module contains the class to find github workflow files.
"""

import os
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderGitHubActions(ConfigFileFinder):
    """
    The class to find dockerfile configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        result = []
        workflows_path = os.path.join(
            path_to_file_system,
            '.github',
            'workflows'
        )
        if os.path.lexists(workflows_path):
            file_list = [
                os.path.join(workflows_path, entry) for entry in os.listdir(workflows_path)
                if entry.endswith('.yaml') or entry.endswith('.yml')
            ]
            for result_file in file_list:
                print(
                    f"{COLOR_CYAN}Found file "
                    f"{result_file.replace(path_to_file_system, '')}"
                    f"{COLOR_TERMINATION}"
                )
            grouped_result_files = cff_util.group_found_files_by_subpath(
                path_to_file_system,
                file_list
            )
            result.extend(
                cff_util.create_grouped_temp_locations_and_manifest_entries(
                    path_to_file_system,
                    grouped_result_files,
                    self.get_service_name(),
                    "action.yml",
                    "yaml"
                )
            )
        return result

    def check_call_command_in_container(
            self,
            path_to_file_system: str,
            docker_config: Dict
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return []

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'github_actions'

ConfigFileFinder.register(ConfigFileFinderGitHubActions)

"""
This module contains the class to find Openafs configurations
inside a folder structure.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderOpenAfs(ConfigFileFinder):
    """
    The class to find openafs configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        There is no standard location for Openafs files. Returning nothing.
        """
        return None
    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["NoAuth", "KeyFile", "UserList", "BosConfig", "ThisCell", "CellServDB"]
        result_files = []
        logging.debug("Trying to find the files by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                matching_file_names = [file_name for file_name in file_names
                                       if standard_name == file_name]
                if matching_file_names:
                    mapped_file_names = [
                        os.path.join(dir_path, file_name)
                        for file_name in matching_file_names
                    ]
                    logging.debug("Found entries: %s",
                                  mapped_file_names)
                    result_files.extend(mapped_file_names)
        results = []
        for result_file in result_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{result_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
        grouped_results = cff_util.group_found_files_by_subpath(
            path_to_file_system,
            result_files
        )
        for grouped_result_files in grouped_results.values():
            results.append(cff_util.create_temp_location_and_manifest_entry_same_service(
                path_to_file_system,
                [
                    (
                        os.path.basename(result_file),
                        result_file,
                        os.path.basename(result_file),
                        "custom"
                    )
                    for result_file in grouped_result_files
                ],
                self.get_service_name(),
            ))
        return results

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
        return 'open_afs'

ConfigFileFinder.register(ConfigFileFinderOpenAfs)

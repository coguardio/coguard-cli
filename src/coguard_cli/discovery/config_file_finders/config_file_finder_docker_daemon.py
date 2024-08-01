"""
This module contains the class to find Docker Daemon configurations
inside a folder structure.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION
import coguard_cli.discovery.config_file_finders as cff_util

class ConfigFileFinderDockerDaemon(ConfigFileFinder):
    """
    The class to find docker_daemon configuration files within a file system.
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
        standard_names = ["daemon.json"]
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                if standard_name in file_names:
                    logging.debug("Found an entry: %s",
                                  os.path.join(dir_path, standard_name))
                    result_files.append(os.path.join(dir_path, standard_name))
        results = []
        for result_file in result_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{result_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
            append_candidate = cff_util.create_temp_location_and_manifest_entry(
                path_to_file_system,
                os.path.basename(result_file),
                result_file,
                'docker_daemon',
                'daemon.json',
                'json'
            )
            if append_candidate is None:
                continue
            results.append(append_candidate)
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
        return 'docker_daemon'

ConfigFileFinder.register(ConfigFileFinderDockerDaemon)

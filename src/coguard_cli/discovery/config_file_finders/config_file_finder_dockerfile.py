"""
This module contains the class to find Dockerfile configurations
inside a folder structure.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderDockerfile(ConfigFileFinder):
    """
    The class to find dockerfile configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_locations = [
            'Dockerfile'
        ]
        locations_on_current_machine = [
            os.path.join(path_to_file_system, entry)
            for entry in standard_locations
        ]
        for location_on_current_machine in locations_on_current_machine:
            if os.path.lexists(location_on_current_machine):
                logging.debug("Found a file in the standard location: %s",
                              location_on_current_machine)
                print(
                    f"{COLOR_CYAN} Found configuration file "
                    f"{location_on_current_machine.replace(path_to_file_system, '')}"
                    f"{COLOR_TERMINATION}"
                )
                file_name = os.path.basename(location_on_current_machine)
                return cff_util.create_temp_location_and_manifest_entry(
                    path_to_file_system,
                    file_name,
                    location_on_current_machine,
                    self.get_service_name(),
                    "Dockerfile",
                    "dockerfile"
                )
        logging.debug("Could not find the file in the standard location.")
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["Dockerfile.*", "^.*\\.[dD]ockerfile$"]
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                #if standard_name in file_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
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
            results.append(cff_util.create_temp_location_and_manifest_entry(
                path_to_file_system,
                os.path.basename(result_file),
                result_file,
                self.get_service_name(),
                "Dockerfile",
                "dockerfile"
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
        return 'dockerfile'

ConfigFileFinder.register(ConfigFileFinderDockerfile)

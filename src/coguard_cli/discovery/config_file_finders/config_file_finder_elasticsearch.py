"""
This module contains the class to find KAFKA configurations
inside a folder structure.
"""

import os
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderElasticsearch(ConfigFileFinder):
    """
    The class to find elasticsearch configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_location ='/etc/elasticsearch/elasticsearch.yml'
        location_on_current_machine = os.path.join(path_to_file_system, standard_location[1:])
        if os.path.lexists(location_on_current_machine):
            print(f"{COLOR_CYAN} Found configuration file {standard_location}{COLOR_TERMINATION}")
            return cff_util.create_temp_location_and_manifest_entry(
                path_to_file_system,
                os.path.basename(standard_location),
                self.get_service_name,
                standard_location,
                "elasticsearch.yml",
                "yaml"
            )
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_name = "elasticsearch.yml"
        result_files = []
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            if standard_name in file_names:
                result_files.append(os.path.join(dir_path, standard_name))
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
                "elasticsearch.yml",
                "yaml"
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
        result_files = cff_util.common_call_command_in_container(
            docker_config,
            r"elasticsearch-server-start.sh\s+([^\s]+)"
        )
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
                os.path.join(path_to_file_system, result_file),
                self.get_service_name(),
                "elasticsearch.yml",
                "yaml"
            ))
        return results

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'elasticsearch'

ConfigFileFinder.register(ConfigFileFinderElasticsearch)

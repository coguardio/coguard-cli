"""
This module contains the class to find Kubernetes configurations
inside a folder structure.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderKubernetes(ConfigFileFinder):
    """
    The class to find kubernetes configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        There is no standard location for Kubernetes files. Returning nothing.
        """
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["^.*\\.ya?ml$"]
        result_files = []
        required_fields = [
            "apiVersion",
            "kind",
            "metadata"
        ]
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
                kubernetes_filter = [file_name for file_name in matching_file_names
                                     if cff_util.does_config_yaml_contain_required_keys(
                                             os.path.join(dir_path, file_name),
                                             required_fields
                                     )]
                if kubernetes_filter:
                    mapped_file_names = [
                        os.path.join(dir_path, file_name)
                        for file_name in kubernetes_filter
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
        grouped_result_files = cff_util.group_found_files_by_subpath(
            path_to_file_system,
            result_files
        )
        results.extend(cff_util.create_grouped_temp_locations_and_manifest_entries(
            path_to_file_system,
            grouped_result_files,
            self.get_service_name(),
            "kube-deployment.yaml",
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
        return []

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'kubernetes'

ConfigFileFinder.register(ConfigFileFinderKubernetes)

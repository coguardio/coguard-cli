"""
This module contains the class to find Terraform configurations
inside a folder structure.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
import hcl2
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderTerraform(ConfigFileFinder):
    """
    The class to find terraform configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        There is no standard location for Terraform files. Returning nothing.
        """
        return None

    def _can_parse_tf_file(self, file_path: str) -> bool:
        """
        Helper function to ensure that a file with ending .tf is indeed parseable
        using Terraform.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file_stream:
                hcl2.load(file_stream)
        #pylint: disable=bare-except
        except:
            logging.debug(
                "Failed to load potential terraform file %s",
                file_path
            )
            return False
        return True


    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["^.*\\.tf$"]
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
                terraform_filter = [
                    file_name for file_name in matching_file_names
                    if self._can_parse_tf_file(
                            os.path.join(dir_path, file_name)
                    )
                ]
                if terraform_filter:
                    mapped_file_names = [
                        os.path.join(dir_path, file_name)
                        for file_name in terraform_filter
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
            "main.tf",
            "hcl2"
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
        return 'terraform'

    def is_cluster_service(self):
        return True


ConfigFileFinder.register(ConfigFileFinderTerraform)

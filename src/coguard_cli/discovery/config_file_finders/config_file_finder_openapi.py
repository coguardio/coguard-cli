"""
This module contains the class to find Open_Api configurations
inside a folder structure.
"""

import os
import logging
import re
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION
import coguard_cli.discovery.config_file_finders as cff_util

class ConfigFileFinderOpenApi(ConfigFileFinder):
    """
    The class to find open_api configuration files within a file system.
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
        standard_names = ["^.*\\.(ya?ml|json)$"]
        result_files = []
        required_fields = [
            "openapi",
            "info"
        ]
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
                joined_filter = [
                    file_name for file_name in matching_file_names
                    if (file_name.endswith("yaml") or file_name.endswith("yml"))
                    and cff_util.does_config_yaml_contain_required_keys(
                        os.path.join(dir_path, file_name),
                        required_fields
                    )] + [
                        file_name for file_name in matching_file_names
                        if file_name.endswith("json")
                        and cff_util.does_config_json_contain_required_keys(
                            os.path.join(dir_path, file_name),
                            required_fields
                        )]
                if joined_filter:
                    mapped_file_names = [
                        os.path.join(dir_path, file_name)
                        for file_name in joined_filter
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
            append_candidate = cff_util.create_temp_location_and_manifest_entry(
                path_to_file_system,
                os.path.basename(result_file),
                result_file,
                'open_api',
                'openapi.json' if result_file.endswith('.json') else 'openapi.yml',
                'json' if result_file.endswith('.json') else 'yaml'
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
        return 'open_api'

ConfigFileFinder.register(ConfigFileFinderOpenApi)

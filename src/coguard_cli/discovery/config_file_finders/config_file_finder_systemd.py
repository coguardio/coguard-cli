"""
This module contains the class to find Systemd configurations
inside a folder structure.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderSystemd(ConfigFileFinder):
    """
    The class to find systemd configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        There is no standard location for Systemd files. Returning nothing.
        """
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = [
            (
                "^.*\\.(service|timer|socket|path|device|mount"
                "|swap|automount|target|slice|scope|snapshot)$"
            )
        ]
        result_files = []
        logging.debug("Trying to find the systemd file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                result_files.extend(
                    [
                        os.path.join(dir_path, file_name)
                        for file_name in file_names
                        if re.match(standard_name, file_name)
                    ]
                )
                if "systemd" in dir_path:
                    result_files.extend([
                        os.path.join(dir_path, file_name)
                        for file_name in file_names
                        if file_name.endswith(".conf")
                    ])
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
        def default_file_name_extractor(inp_str: str) -> str:
            """
            The function for extraction to pass to
            create_grouped_temp_locations_and_manifest_entries.
            """
            if inp_str.endswith(".conf"):
                return "systemd-system.conf"
            file_name_match = re.match(
                ("^.*\\.(service|timer|socket|path|device|mount"
                 "|swap|automount|target|slice|scope|snapshot)$"),
                inp_str
            )
            type_match = file_name_match.group(1)
            return f"{type_match}.{type_match}"
        results.extend(cff_util.create_grouped_temp_locations_and_manifest_entries(
            path_to_file_system,
            grouped_result_files,
            self.get_service_name(),
            default_file_name_extractor,
            "ini"
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
        return 'systemd'

ConfigFileFinder.register(ConfigFileFinderSystemd)

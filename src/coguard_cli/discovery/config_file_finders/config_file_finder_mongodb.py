"""
This module contains the class to find MONGODB configurations
inside a folder structure.
"""

import os
import tempfile
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderMongodb(ConfigFileFinder):
    """
    The class to find mongodb configuration files within a file system.
    """

    def create_empty_file_for_default(self) -> Tuple[Dict, str]:
        """
        Helper function to create an empty file to check for default values.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-mongodb")
        with open(
                os.path.join(
                    temp_location,
                    "mongod.conf"
                ),
                'w',
                encoding='utf-8') as empty_file:
            empty_file.write("# Empty config file to represent defaults")
        manifest_entry = {
            "version": "1.0",
            "serviceName": "mongodb",
            "configFileList": [
                {
                    "fileName": "mongod.conf",
                    "defaultFileName": "mongod.conf",
                    "subPath": ".",
                    "configFileType": "yaml"
                }
            ],
            "complimentaryFileList": []
        }
        return (
            manifest_entry,
            temp_location
        )

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_location ='/etc/mongod.conf'
        location_on_current_machine = os.path.join(path_to_file_system, standard_location[1:])
        if os.path.lexists(location_on_current_machine):
            print(f"{COLOR_CYAN} Found configuration file {standard_location}{COLOR_TERMINATION}")
            return cff_util.create_temp_location_and_manifest_entry(
                path_to_file_system,
                "mongod.conf",
                location_on_current_machine,
                self.get_service_name(),
                "mongod.conf",
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
        standard_name = "mongod.conf"
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
                "mongod.conf",
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
            r"mongod.*--config\s+([^\s]+)"
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
                "mongod.conf",
                "yaml"
            ))
        empty_call_result = cff_util.common_call_command_in_container(
            docker_config,
            r"(mongod)"
        )
        if empty_call_result:
            print(
                f"{COLOR_CYAN}Found empty mongod call with no config parameter."
                f" Assuming default values. {COLOR_TERMINATION}"
            )
            results.append(self.create_empty_file_for_default())
        return results

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'mongodb'

ConfigFileFinder.register(ConfigFileFinderMongodb)

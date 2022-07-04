"""
This module contains the class to find APACHE configurations
inside a folder structure.
"""

import os
import shutil
import tempfile
from typing import Dict, List, Optional, Tuple
from coguard_cli.image_check.config_file_finder_abc import ConfigFileFinder
import coguard_cli.image_check.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderApache(ConfigFileFinder):
    """
    The class to find apache configuration files within a file system.
    """

    def _create_temp_location_and_mainfest_entry(
            self,
            path_to_file_system: str,
            location_on_current_machine: str) -> Tuple[Dict, str]:
        """
        Common helper function which creates a temporary folder location for the
        configuration files, and then analyzes include directives. It returns
        a tuple containing a manifest for an apache service and the path to the
        temporary location.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-apache")
        to_copy = cff_util.get_path_behind_symlinks(
            path_to_file_system,
            location_on_current_machine
        )
        file_name = os.path.basename(location_on_current_machine)
        shutil.copy(
            to_copy,
            os.path.join(
                temp_location,
                file_name
            )
        )
        manifest_entry = {
            "version": "1.0",
            "serviceName": "apache",
            "configFileList": [
                {
                    "fileName": file_name,
                    "defaultFileName": "httpd.conf",
                    "subPath": ".",
                    "configFileType": "httpd"
                }
            ],
            "complimentaryFileList": []
        }
        cff_util.extract_include_directives(
            path_to_file_system,
            location_on_current_machine,
            temp_location,
            manifest_entry,
            "httpd",
            r'Include\s+"?(.*?)"?\s*;'
        )
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
        standard_location ='/etc/httpd/conf/httpd.conf'
        location_on_current_machine = os.path.join(path_to_file_system, standard_location[1:])
        if os.path.lexists(location_on_current_machine):
            print(f"{COLOR_CYAN} Found configuration file {standard_location}{COLOR_TERMINATION}")
            return self._create_temp_location_and_mainfest_entry(
                path_to_file_system,
                location_on_current_machine
            )
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["httpd.conf", "apache2.conf"]
        result_files = []
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                if standard_name in file_names:
                    result_files.append(os.path.join(dir_path, standard_name))
        results = []
        for result_file in result_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{result_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
            results.append(self._create_temp_location_and_mainfest_entry(
                path_to_file_system,
                result_file
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
            r"httpd.*-f\s+([^\s]+)"
        )
        results = []
        for result_file in result_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{result_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
            results.append(self._create_temp_location_and_mainfest_entry(
                path_to_file_system,
                os.path.join(path_to_file_system, result_file)
            ))
        return results

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'apache'

ConfigFileFinder.register(ConfigFileFinderApache)

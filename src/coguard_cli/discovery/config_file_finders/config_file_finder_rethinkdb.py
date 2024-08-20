"""
This module contains the class to find Rethinkdb configurations
inside a folder structure.
"""

import json
import os
import shutil
import tempfile
import logging
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION
from coguard_cli.util import convert_string_to_posix_path

class ConfigFileFinderRethinkdb(ConfigFileFinder):
    """
    The class to find rethinkdb configuration files within a file system.
    """

    def _create_temp_location_and_manifest_entry(
            self,
            path_to_file_system: str,
            file_name: str,
            location_on_current_machine: str) -> Optional[Tuple[Dict, str]]:
        """
        Common helper function which creates a temporary folder location for the
        configuration files, and then analyzes include directives. It returns
        a tuple containing a manifest for a rethinkdb service and the path to the
        temporary location.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-rethinkdb")
        to_copy = cff_util.get_path_behind_symlinks(
            path_to_file_system,
            location_on_current_machine
        )
        if not os.path.exists(to_copy):
            logging.error("Could not find the file or resolve the symlink at `%s`",
                          location_on_current_machine)
            return None
        # The reason we added os.sep at the end is because the file location may be
        # at the root of the path_to_file_system. In this case, if there is a separation
        # character at the end of path_to_file_system, the replace may not work.
        # That is why we just add it here.
        loc_within_machine = (os.path.dirname(location_on_current_machine)+os.sep).replace(
            path_to_file_system,
            ''
        )
        loc_within_machine = loc_within_machine[1:] \
            if loc_within_machine.startswith(os.sep) \
               else loc_within_machine
        os.makedirs(os.path.join(temp_location, loc_within_machine), exist_ok=True)
        shutil.copy(to_copy,
                    os.path.join(
                        temp_location,
                        loc_within_machine,
                        os.path.basename(location_on_current_machine)
                    ))
        manifest_entry = {
            "version": "1.0",
            "serviceName": "rethinkdb",
            "configFileList": [
                {
                    "fileName": file_name,
                    "defaultFileName": "default.conf",
                    "subPath": f"./{convert_string_to_posix_path(loc_within_machine)}",
                    "configFileType": "properties"
                }
            ],
            "complimentaryFileList": []
        }
        return (
            manifest_entry,
            temp_location
        )

    def create_empty_file_for_default(self) -> Tuple[Dict, str]:
        """
        Helper function to create an empty file to check for default values.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-rethinkdb")
        with open(
                os.path.join(
                    temp_location,
                    "default.conf"
                ),
                'w',
                encoding='utf-8') as empty_file:
            empty_file.write("# Empty config file to represent defaults")
        manifest_entry = {
            "version": "1.0",
            "serviceName": "rethinkdb",
            "configFileList": [
                {
                    "fileName": "default.conf",
                    "defaultFileName": "default.conf",
                    "subPath": ".",
                    "configFileType": "properties"
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
        logging.debug("Attempting to find the rethinkdbql.conf file in the standard location.")
        standard_location = '/etc/rethinkdb/default.conf'
        location_on_current_machine = os.path.join(path_to_file_system, standard_location[1:])
        temp_location_tuple = None
        if os.path.lexists(location_on_current_machine):
            file_name = os.path.basename(location_on_current_machine)
            print(f"{COLOR_CYAN} Found configuration file {standard_location}{COLOR_TERMINATION}")
            temp_location_tuple = self._create_temp_location_and_manifest_entry(
                path_to_file_system,
                file_name,
                location_on_current_machine
            )
        return temp_location_tuple

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["default.conf"]
        result_files = []
        logging.debug("Attempting to find the standard names in the file system")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                logging.debug("Checking if %s is in %s",
                              standard_name,
                              json.dumps(file_names))
                if standard_name in file_names and 'rethinkdb' in dir_path:
                    result_files.append(os.path.join(dir_path, standard_name))
        logging.debug("Found the following files with standard names in the file system: %s",
                      result_files)
        results = []
        for result_file in result_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{result_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
            append_candidate = self._create_temp_location_and_manifest_entry(
                path_to_file_system,
                os.path.basename(result_file),
                result_file
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
        result_files = cff_util.common_call_command_in_container(
            docker_config,
            r".*rethinkdb.*\s+--config-file(=|\s+)([^\s]+)"
        )
        results = []
        for result_file in result_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{result_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
            results.append(self._create_temp_location_and_manifest_entry(
                path_to_file_system,
                os.path.basename(result_file),
                os.path.join(path_to_file_system, result_file)
            ))
        empty_call_result = cff_util.common_call_command_in_container(
            docker_config,
            r"(rethinkdb)"
        )
        if not results and empty_call_result:
            print(
                f"{COLOR_CYAN}Found empty rethinkdb call with no config parameter."
                f" Assuming default values. {COLOR_TERMINATION}"
            )
            results.append(self.create_empty_file_for_default())
        return results

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'rethinkdb'

ConfigFileFinder.register(ConfigFileFinderRethinkdb)

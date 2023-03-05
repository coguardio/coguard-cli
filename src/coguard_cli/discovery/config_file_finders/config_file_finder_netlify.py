"""
This module contains the class to find Netlify configurations
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

class ConfigFileFinderNetlify(ConfigFileFinder):
    """
    The class to find netlify configuration files within a file system.
    """

    def _create_temp_location_and_manifest_entry(
            self,
            path_to_file_system: str,
            file_name: str,
            location_on_current_machine: str) -> Optional[Tuple[Dict, str]]:
        """
        Common helper function which creates a temporary folder location for the
        configuration files. It returns
        a tuple containing a manifest for a netlify service and the path to the
        temporary location.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-netlify")
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
        os.makedirs(os.path.join(temp_location, loc_within_machine),
                    exist_ok=True)
        shutil.copy(to_copy,
                    os.path.join(
                        temp_location,
                        loc_within_machine,
                        os.path.basename(location_on_current_machine)
                    ))
        manifest_entry = {
            "version": "1.0",
            "serviceName": "netlify",
            "configFileList": [
                {
                    "fileName": file_name,
                    "defaultFileName": file_name,
                    "subPath": f".{os.sep}{loc_within_machine}",
                    "configFileType": "toml" if file_name == "netlify.toml" else "custom"
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
        logging.debug("Attempting to find the netlify.toml file in the standard location.")
        standard_location = 'netlify.conf'
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
        if temp_location_tuple is not None:
            headers_location = '_headers'
            headers_on_current_machine = os.path.join(path_to_file_system, headers_location[1:])
            if os.path.lexists(headers_on_current_machine):
                print(
                    f"{COLOR_CYAN} Found configuration file {headers_location}{COLOR_TERMINATION}"
                )
                to_copy = cff_util.get_path_behind_symlinks(
                    path_to_file_system,
                    headers_on_current_machine
                )
                shutil.copy(to_copy,
                            os.path.join(
                                temp_location_tuple[1],
                                os.path.basename(headers_on_current_machine)
                            ))
                temp_location_tuple[0]["configFileList"].append(
                    {
                        "fileName": "_headers",
                        "defaultFileName": "_headers",
                        "subPath": ".",
                        "configFileType": "custom"
                    }
                )
            return temp_location_tuple
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["netlify.toml", "_headers"]
        result_files = []
        logging.debug("Attempting to find the standard names in the file system")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                logging.debug("Checking if %s is in %s",
                              standard_name,
                              json.dumps(file_names))
                if standard_name in file_names:
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
        return []

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'netlify'

    def is_cluster_service(self):
        return True

ConfigFileFinder.register(ConfigFileFinderNetlify)

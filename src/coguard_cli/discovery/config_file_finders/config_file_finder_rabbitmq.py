"""
This module contains the class to find Rabbitmq configurations
inside a folder structure.
"""

import os
import shutil
import tempfile
import logging
from typing import Dict, List, Optional, Tuple
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION
from coguard_cli.util import convert_string_to_posix_path

class ConfigFileFinderRabbitmq(ConfigFileFinder):
    """
    The class to find rabbitmq configuration files within a file system.
    """

    def _create_temp_location_and_manifest_entry(
            self,
            path_to_file_system: str,
            file_name: str,
            location_on_current_machine: str) -> Optional[Tuple[Dict, str]]:
        """
        Common helper function which creates a temporary folder location for the
        configuration files, and then analyzes include directives. It returns
        a tuple containing a manifest for a rabbitmq service and the path to the
        temporary location.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-rabbitmq")
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
        shutil.copy(
            to_copy,
            os.path.join(
                temp_location,
                loc_within_machine,
                os.path.basename(location_on_current_machine)
            )
        )
        manifest_entry = {
            "version": "1.0",
            "serviceName": "rabbitmq",
            "configFileList": [
                {
                    "fileName": file_name,
                    "defaultFileName": "rabbitmq.conf",
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
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-rabbitmq")
        with open(
                os.path.join(
                    temp_location,
                    "rabbitmq.conf"
                ),
                'w',
                encoding='utf-8') as empty_file:
            empty_file.write("# Empty config file to represent defaults")
        manifest_entry = {
            "version": "1.0",
            "serviceName": "rabbitmq",
            "configFileList": [
                {
                    "fileName": "rabbitmq.conf",
                    "defaultFileName": "rabbitmq.conf",
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
        standard_locations = [
            '/etc/rabbitmq/rabbitmq.conf'
        ]
        locations_on_current_machine = [
            os.path.join(path_to_file_system, entry[1:])
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
                return self._create_temp_location_and_manifest_entry(
                    path_to_file_system,
                    file_name,
                    location_on_current_machine
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
        standard_names = ["rabbitmq.conf"]
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                if standard_name in file_names:
                    logging.debug("Found an entry: %s",
                                  os.path.join(dir_path, standard_name))
                    result_files.append(os.path.join(dir_path, standard_name))
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

    def extract_potential_config_file_from_env_var(
            self,
            path_to_file_system: str,
            docker_config: Dict
    ) -> Optional[Tuple[Dict, str]]:
        """
        Helper function since RabbitMQ can specify the config file through an environment
        variable.
        """
        env_entry = docker_config.get("Config", {}).get("Env", [])
        if env_entry is None:
            env_entry = []
        env_entry = env_entry if isinstance(env_entry, list) \
            else [env_entry]
        if not env_entry:
            return None
        result_file_entry = None
        for env_var in env_entry:
            if env_var.startswith("RABBITMQ_CONFIG_FILE="):
                result_file_entry = env_var.replace("RABBITMQ_CONFIG_FILE=", "")
        if not result_file_entry:
            return None
        if not os.path.exists(os.path.join(path_to_file_system, result_file_entry)):
            return None
        return self._create_temp_location_and_manifest_entry(
            path_to_file_system,
            os.path.basename(result_file_entry),
            os.path.join(path_to_file_system, result_file_entry)
        )

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
            r"rabbitmq-server\s+([^-]{1,2}[^\s]+)"
        )
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
                os.path.join(path_to_file_system, result_file)
            )
            if append_candidate is None:
                continue
            results.append(append_candidate)
        empty_call_result = cff_util.common_call_command_in_container(
            docker_config,
            r"(rabbitmq-server)"
        )
        if empty_call_result:
            config_file = self.extract_potential_config_file_from_env_var(
                path_to_file_system,
                docker_config
            )
            if config_file:
                results.append(config_file)
            else:
                print(
                    f"{COLOR_CYAN}Found empty rabbitmq call with no config parameter."
                    f" Assuming default values. {COLOR_TERMINATION}"
                )
                results.append(self.create_empty_file_for_default())
        return results

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'rabbitmq'

ConfigFileFinder.register(ConfigFileFinderRabbitmq)

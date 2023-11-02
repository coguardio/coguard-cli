"""
This module contains the class to find OpenTelemetry Collector configurations
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

class ConfigFileFinderOpenTelemetryCollector(ConfigFileFinder):
    """
    The class to find OpenTelemetry configuration files within a file system.
    """

    def _create_temp_location_and_manifest_entry(
            self,
            path_to_file_system: str,
            file_name_and_current_location: Tuple[str, str],
            input_temp_location = None,
            current_manifest_entry = None) -> Tuple[Dict, str]:
        """
        Common helper function which creates a temporary folder location for the
        configuration files, if not yest existent. It returns
        a tuple containing a manifest for a OpenTelemetry service and the path to the
        temporary location.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-otel-collector") \
            if input_temp_location is None else input_temp_location
        (file_name, location_on_current_machine) = file_name_and_current_location
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
            "serviceName": "opentelemetry_collector",
            "configFileList": [],
            "complimentaryFileList": []
        } if current_manifest_entry is None else current_manifest_entry
        manifest_entry["configFileList"].append({
            "fileName": file_name,
            "defaultFileName": "config.yaml",
            "subPath": f"./{convert_string_to_posix_path(loc_within_machine)}",
            "configFileType": "yaml"
        })
        return (
            manifest_entry,
            temp_location
        )

    def _create_or_update_temp_location(
            self,
            path_to_file_system: str,
            config_file_path: str,
            temp_location_tuple_inp: Optional[Tuple[Dict, str]] = None):
        """
        This helper function takes in the path to the file system,
        a configuration file path, and an optional tuple containing
        manifest infrmation and the path to a temporary directory.
        If the file represented by config_file_path can be found,
        it copies the file to the temp location and updates or creates
        a manifest entry.
        """
        location_on_current_machine = os.path.join(path_to_file_system, config_file_path[1:])
        temp_location_tuple = temp_location_tuple_inp
        if os.path.lexists(location_on_current_machine):
            file_name = os.path.basename(location_on_current_machine)
            print(f"{COLOR_CYAN} Found configuration file {config_file_path}{COLOR_TERMINATION}")
            if temp_location_tuple is None:
                temp_location_tuple = self._create_temp_location_and_manifest_entry(
                    path_to_file_system,
                    (file_name, location_on_current_machine)
                )
            else:
                temp_location_tuple = self._create_temp_location_and_manifest_entry(
                    path_to_file_system,
                    (file_name, location_on_current_machine),
                    temp_location_tuple[1],
                    temp_location_tuple[0]
                )
        return temp_location_tuple


    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        config_files_in_standard_locations = [
            '/etc/otelcol/config.yaml',
        ]
        logging.debug("Attempting to find all the OpenTelemetry "
                      "configurations in standard location")
        temp_location_tuple = None
        for config_file in config_files_in_standard_locations:
            temp_location_tuple = self._create_or_update_temp_location(
                path_to_file_system,
                config_file,
                temp_location_tuple
            )
        if temp_location_tuple is None:
            return temp_location_tuple
        return temp_location_tuple

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        file_candidates = []
        logging.debug("Attempting to find yaml files with respective keys in filesystem")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            logging.debug("Checking if a yaml is in %s",
                          json.dumps(file_names))
            file_candidates.extend([os.path.join(dir_path, file_name) for file_name in file_names
                                    if file_name.endswith(".yml") or file_name.endswith(".yaml")])
        logging.debug("Found the following yaml files in the file system: %s",
                      file_candidates)
        result_files = []
        keys_to_look_for = [
            "receivers",
            "exporters",
            "service"
        ]
        results = []
        for file_candidate in file_candidates:
            file_candidate_without_symlink = cff_util.get_path_behind_symlinks(
                '',
                file_candidate
            )
            if not os.path.exists(file_candidate_without_symlink) or \
               not file_candidate_without_symlink.startswith(path_to_file_system):
                logging.error("The symlink of `%s` did not lead to a valid file inside the folder",
                              file_candidate)
                continue
            with open(file_candidate_without_symlink, 'r', encoding='utf-8') as f_handle:
                f_content = f_handle.read()
            if all(key in f_content for key in keys_to_look_for):
                result_files.append(file_candidate_without_symlink)
        for result_file in result_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{result_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
            append_candidate = self._create_temp_location_and_manifest_entry(
                path_to_file_system,
                (os.path.basename(result_file), result_file)
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
        # There is no clear call command to look for, since the libraries
        # and executables can be very custom. Everything needs to be found
        # in the other two functions.
        return []

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'opentelemetry_collector'

ConfigFileFinder.register(ConfigFileFinderOpenTelemetryCollector)

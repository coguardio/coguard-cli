"""
This module contains the class to find Kubernetes configurations
inside a folder structure.
"""

import os
import re
import shutil
import tempfile
import logging
from typing import Dict, List, Optional, Tuple
import yaml
from flatten_dict import unflatten
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderKubernetes(ConfigFileFinder):
    """
    The class to find kubernetes configuration files within a file system.
    """

    def _create_temp_location_and_mainfest_entry(
            self,
            path_to_file_system: str,
            file_name: str,
            location_on_current_machine: str) -> Tuple[Dict, str]:
        """
        Common helper function which creates a temporary folder location for the
        configuration files, and then analyzes include directives. It returns
        a tuple containing a manifest for a kubernetes service and the path to the
        temporary location.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-kubernetes")
        to_copy = cff_util.get_path_behind_symlinks(
            path_to_file_system,
            location_on_current_machine
        )
        shutil.copy(
            to_copy,
            os.path.join(
                temp_location,
                os.path.basename(location_on_current_machine)
            )
        )
        manifest_entry = {
            "version": "1.0",
            "serviceName": "kubernetes",
            "configFileList": [
                {
                    "fileName": file_name,
                    "defaultFileName": "kube-deployment.yaml",
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
        There is no standard location for Kubernetes files. Returning nothing.
        """
        return None

    def _is_file_kubernetes_yaml(self, file_path: str) -> bool:
        """
        The helper function to determine if a given file can be heuristically
        determined to be a Kubernetes file.
        """
        required_fields = [
            "apiVersion",
            "kind",
            "metadata",
            "spec"
        ]
        config = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file_stream:
                config_res = yaml.safe_load_all(file_stream)
                config = [] if config_res is None else [
                    unflatten(config_part, splitter='dot') for config_part in config_res
                ]
        #pylint: disable=bare-except
        except:
            logging.error(
                "Failed to load %s",
                file_path
            )
            return False
        return all(required_field in config_instance
                   for config_instance in config
                   for required_field in required_fields)


    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = [".*\\.ya?ml"]
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                #if standard_name in file_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
                kubernetes_filter = [file_name for file_name in matching_file_names
                                     if self._is_file_kubernetes_yaml(
                                             os.path.join(dir_path, file_name)
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
            results.append(self._create_temp_location_and_mainfest_entry(
                path_to_file_system,
                os.path.basename(result_file),
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
        return []

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'kubernetes'

ConfigFileFinder.register(ConfigFileFinderKubernetes)

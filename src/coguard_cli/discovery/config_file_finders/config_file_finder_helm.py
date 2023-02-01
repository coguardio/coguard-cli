"""
This module contains the class to find Helm configurations
inside a folder structure.
"""

import os
import re
import tempfile
import logging
from typing import Dict, List, Optional, Tuple
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION
from coguard_cli import docker_dao

class ConfigFileFinderHelm(ConfigFileFinder):
    """
    The class to find helm configuration files within a file system.
    """

    def _create_temp_location_and_mainfest_entry(
            self,
            helm_chart_file: str):
        """
        Helper function to extract the Helm charts from a file system and
        put it into a folder.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-helm")
        kubernetes_file_content = docker_dao.get_kubernetes_translation_from_helm(
            os.path.dirname(helm_chart_file)
        )
        logging.debug("The content to write: %s", kubernetes_file_content)
        file_name = "kube-deployment.yaml"
        with open(
                os.path.join(temp_location, file_name),
                'w',
                encoding='utf-8'
        ) as kube_file:
            kube_file.write(kubernetes_file_content)
        manifest_entry = {
            "version": "1.0",
            "serviceName": self.get_service_name(),
            "configFileList": [
                {
                    "fileName": file_name,
                    "defaultFileName": file_name,
                    "subPath": ".",
                    "configFileType": "yaml"
                }
            ],
            "complimentaryFileList": []
        }
        return(
            manifest_entry,
            temp_location
        )

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        There is no standard location for Helm files. Returning nothing.
        """
        return None

    def _find_charts_files(self, path_to_file_system: str) -> List[str]:
        """
        Helper function to find Helm charts.
        """
        standard_names = ["Chart.ya?ml"]
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        required_fields = [
            "apiVersion",
            "name",
            "version"
        ]
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
                helm_filter = [
                    file_name for file_name in matching_file_names
                    if cff_util.does_config_yaml_contain_required_keys(
                        os.path.join(dir_path, file_name),
                        required_fields
                    )]
                if helm_filter:
                    mapped_file_names = [
                        os.path.join(dir_path, file_name)
                        for file_name in helm_filter
                    ]
                    logging.debug("Found entries: %s",
                                  mapped_file_names)
                    result_files.extend(mapped_file_names)
        return result_files

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        result_files = []
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        helm_chart_files = self._find_charts_files(path_to_file_system)
        for helm_chart_file in helm_chart_files:
            print(
                f"{COLOR_CYAN}Found file "
                f"{helm_chart_file.replace(path_to_file_system, '')}"
                f"{COLOR_TERMINATION}"
            )
            result_files.append(self._create_temp_location_and_mainfest_entry(
                helm_chart_file
            ))
        return result_files

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

ConfigFileFinder.register(ConfigFileFinderHelm)
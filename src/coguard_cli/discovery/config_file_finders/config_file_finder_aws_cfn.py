"""
This module contains the class to find Cloudformation configurations
inside a folder structure.
"""

import os
import re
import logging
import json
from typing import Dict, List, Optional, Tuple
from flatten_dict import unflatten
import yaml
from cfn_tools import load_yaml, load_json, dump_yaml, dump_json
from coguard_cli.discovery.config_file_finder_abc import ConfigFileFinder
import coguard_cli.discovery.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderCloudformation(ConfigFileFinder):
    """
    The class to find cloudformation configuration files within a file system.
    """

    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        There is no standard location for Cloudformation files. Returning nothing.
        """
        return None

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["^.*\\.ya?ml$", "^.*\\.json$", "^.*\\.template$"]
        result_files = []
        required_fields = [
            "Resources"
        ]
        logging.debug("Trying to find the file by searching"
                      " for the standard name in the filesystem.")
        for (dir_path, _, file_names) in os.walk(path_to_file_system):
            for standard_name in standard_names:
                matching_file_names = [file_name for file_name in file_names
                                       if re.match(standard_name, file_name)]
                cloudformation_filter = [file_name for file_name in matching_file_names
                                         if self.does_config_contain_required_keys(
                                                 os.path.join(dir_path, file_name),
                                                 required_fields
                                     )]
                if cloudformation_filter:
                    mapped_file_names = [
                        os.path.join(dir_path, file_name)
                        for file_name in cloudformation_filter
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
        yaml_result_files = [
            result_file for result_file in result_files
            if result_file.endswith('.yaml') or
            result_file.endswith('.yml')
        ]
        other_result_files = [
            result_file for result_file in result_files
            if not (result_file.endswith('.yaml') or
                    result_file.endswith('.yml'))
        ]
        grouped_yaml_result_files = cff_util.group_found_files_by_subpath(
            path_to_file_system,
            yaml_result_files
        )
        grouped_other_result_files = cff_util.group_found_files_by_subpath(
            path_to_file_system,
            other_result_files
        )
        results.extend(cff_util.create_grouped_temp_locations_and_manifest_entries(
            path_to_file_system,
            grouped_yaml_result_files,
            self.get_service_name(),
            "aws_template.yaml",
            "aws_cfn"
        ))
        results.extend(cff_util.create_grouped_temp_locations_and_manifest_entries(
            path_to_file_system,
            grouped_other_result_files,
            self.get_service_name(),
            "aws_template.json",
            "aws_cfn"
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
        return 'cloudformation'

    def does_config_contain_required_keys(
            self,
            file_path: str,
            required_fields: List[str]
    ) -> bool:
        """
        Helper function to check if a yaml/json file as defined by `file_path` contains a set of
        mandatory keys as provided by `required_fields`.
        """
        logging.debug("Parsing %s using the aws_cfn-file-type parser",
                      file_path)
        try:
            with open(os.path.join(file_path), 'r', encoding='utf-8') as file_stream:
                temp_dict = load_yaml(file_stream)
                config_res = yaml.safe_load_all(dump_yaml(temp_dict))
                config = [] if config_res is None else config_res
                config = [unflatten(cfg, splitter='dot') for cfg in config]
        # pylint: disable=bare-except
        except:
            try:
                with open(os.path.join(file_path), 'r', encoding='utf-8') as file_stream:
                    temp_dict = load_json(file_stream.read())
                config_res = json.loads(dump_json(temp_dict))
                config = {} if config_res is None else config_res
                config = unflatten(config, splitter='dot')
            # pylint: disable=bare-except
            except:
                logging.debug(
                    "Failed to load %s",
                    file_path
                )
                return False
        # The next line is to recognize flattened values in aws_cfn files and expand them
        if isinstance(config, dict):
            config = [config]
        return config and all(config_instance and required_field in config_instance
                              for config_instance in config
                              for required_field in required_fields)

    def is_cluster_service(self):
        return True

ConfigFileFinder.register(ConfigFileFinderCloudformation)

"""
This module contains the class to find Tomcat configurations
inside a folder structure.
"""

import json
import os
import shutil
import tempfile
import logging
from typing import Dict, List, Optional, Tuple
from functools import reduce
from coguard_cli.image_check.config_file_finder_abc import ConfigFileFinder
import coguard_cli.image_check.config_file_finders as cff_util
from coguard_cli.print_colors import COLOR_CYAN, COLOR_TERMINATION

class ConfigFileFinderTomcat(ConfigFileFinder):
    """
    The class to find tomcat configuration files within a file system.
    """

    def _create_temp_location_and_mainfest_entry(
            self,
            path_to_file_system: str,
            file_name_and_current_location: Tuple[str, str],
            input_temp_location = None,
            current_manifest_entry = None) -> Tuple[Dict, str]:
        """
        Common helper function which creates a temporary folder location for the
        configuration files, if not yest existent. It returns
        a tuple containing a manifest for a tomcat service and the path to the
        temporary location.
        """
        temp_location = tempfile.mkdtemp(prefix="coguard-cli-tomcat") \
            if input_temp_location is None else input_temp_location
        (file_name, location_on_current_machine) = file_name_and_current_location
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
            "serviceName": "tomcat",
            "configFileList": [],
            "complimentaryFileList": []
        } if current_manifest_entry is None else current_manifest_entry
        manifest_entry["configFileList"].append({
            "fileName": file_name,
            "defaultFileName": file_name,
            "subPath": ".",
            "configFileType": "xml"
        })
        return (
            manifest_entry,
            temp_location
        )

    def extract_web_xmls(
            self,
            path_to_file_system: str,
            path_to_potential_location: str,
            temp_location_tuple: Tuple[Dict, str]):
        """
        Helper function to extract the multiple potential web xml files
        in the filesystem and include them into the temp_location.
        """
        web_xml_paths = []
        for (dir_name, _, file_names) in os.walk(path_to_potential_location):
            if "web.xml" in file_names:
                web_xml_paths.append(os.path.join(
                    dir_name,
                    "web.xml"
                ))
        for web_xml_path in web_xml_paths:
            path_within_temp_location = web_xml_path.replace(path_to_potential_location, '')
            subdir = os.path.dirname(path_within_temp_location)
            if subdir.startswith(os.path.sep):
                subdir = subdir[1:]
            to_copy = cff_util.get_path_behind_symlinks(
                path_to_file_system,
                web_xml_path
            )
            new_location = os.path.join(temp_location_tuple[1], subdir)
            os.makedirs(new_location, exist_ok=True)
            shutil.copy(
                to_copy,
                new_location
            )
            temp_location_tuple[0]["configFileList"].append({
                "fileName": "web.xml",
                "defaultFileName": "web.xml",
                "subPath": subdir,
                "configFileType": "xml"
            })


    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        config_files_in_standard_locations = [
            '/usr/local/tomcat/conf/server.xml',
            '/usr/local/tomcat/conf/web.xml',
            '/usr/local/tomcat/conf/context.xml',
        ]
        web_xml_root_path = '/usr/local/tomcat/webapps'
        logging.debug("Attempting to find all the Tomcat configurations in standard location")
        temp_location_tuple = None
        for config_file in config_files_in_standard_locations:
            location_on_current_machine = os.path.join(path_to_file_system, config_file[1:])
            if os.path.lexists(location_on_current_machine):
                file_name = os.path.basename(location_on_current_machine)
                print(f"{COLOR_CYAN} Found configuration file {config_file}{COLOR_TERMINATION}")
                if temp_location_tuple is None:
                    temp_location_tuple = self._create_temp_location_and_mainfest_entry(
                        path_to_file_system,
                        (file_name, location_on_current_machine)
                    )
                else:
                    temp_location_tuple = self._create_temp_location_and_mainfest_entry(
                        path_to_file_system,
                        (file_name, location_on_current_machine),
                        temp_location_tuple[1],
                        temp_location_tuple[0]
                    )
        if temp_location_tuple is None:
            return temp_location_tuple
        self.extract_web_xmls(
            path_to_file_system,
            os.path.join(path_to_file_system, web_xml_root_path[1:]),
            temp_location_tuple
        )
        return temp_location_tuple

    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        standard_names = ["server.xml", "web.xml", "context.xml"]
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
            results.append(self._create_temp_location_and_mainfest_entry(
                path_to_file_system,
                (os.path.basename(result_file), result_file)
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
        env_vars = docker_config.get(
            "Config",
            {}
        ).get(
            "Env",
            []
        )
        catalina_home = reduce(
            lambda acc, env_var: env_var.split("=")[1] \
            if env_var.split("=")[0] == "CATALINA_HOME" else acc,
            env_vars,
            ""
        )
        results = []
        if catalina_home:
            config_files_in_standard_locations = [
                os.path.join(catalina_home, 'conf/server.xml'),
                os.path.join(catalina_home, 'conf/web.xml'),
                os.path.join(catalina_home, 'conf/context.xml'),
            ]
            web_xml_root_path = os.path.join(catalina_home, 'webapps')
            logging.debug(
                "Attempting to find all the Tomcat configurations in CATALINA_HOME location"
            )
            temp_location_tuple = None
            for config_file in config_files_in_standard_locations:
                location_on_current_machine = os.path.join(path_to_file_system, config_file[1:])
                if os.path.lexists(location_on_current_machine):
                    file_name = os.path.basename(location_on_current_machine)
                    print(f"{COLOR_CYAN} Found configuration file {config_file}{COLOR_TERMINATION}")
                    if temp_location_tuple is None:
                        temp_location_tuple = self._create_temp_location_and_mainfest_entry(
                            path_to_file_system,
                            (file_name, location_on_current_machine)
                        )
                    else:
                        temp_location_tuple = self._create_temp_location_and_mainfest_entry(
                            path_to_file_system,
                            (file_name, location_on_current_machine),
                            temp_location_tuple[1],
                            temp_location_tuple[0]
                        )
            if temp_location_tuple is None:
                return results
            self.extract_web_xmls(
                path_to_file_system,
                os.path.join(path_to_file_system, web_xml_root_path[1:]),
                temp_location_tuple
            )
            results.append(temp_location_tuple)
        return results

    def get_service_name(self) -> str:
        """
        See the documentation of ConfigFileFinder for reference.
        """
        return 'tomcat'

ConfigFileFinder.register(ConfigFileFinderTomcat)

"""
This module contains the abstract base class for the configuration file finding process.
For every service, we define a child-class of this abstract base class,
which implements the extraction of the respective configurations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from coguard_cli.print_colors import COLOR_TERMINATION, COLOR_YELLOW

class ConfigFileFinder(ABC):
    """
    This is an abstract base class for finding configuration files in
    a filesystem.

    For every service, we define a child-class finding the different configuration
    files.

    The main purpose of this class is to categorize those later inside a factory
    and being able to iterate through them.
    """

    @abstractmethod
    def check_for_config_files_in_standard_location(
            self, path_to_file_system: str
    ) -> Optional[Tuple[Dict, str]]:
        """
        This is supposed to be the function where we search
        in standard locations for configuration files and compile them
        together.

        This needs to be overwritten by the respective child-class.

        Returns an optional tuple as described in :func:`find_configuration_files`.

        :param path_to_file_system: The path where the local filesystem of the image is stored.
        :returns: A Tuple containing a dictionary, which represents the service manifest entry for
                  the software represented by the :class:`ConfigFileFinder` instance, and
                  a string representing the path where the discovered configuration files are
                  stored. If nothing was found, None is returned.
        """

    @abstractmethod
    def check_for_config_files_filesystem_search(
            self,
            path_to_file_system: str
    ) -> List[Tuple[Dict, str]]:
        """
        This is searching for the default name of the respective service
        anywhere on the file-system. This may catch multiple configuration files,
        which then need to be accounted for separately, having potential
        false-positives.

        This needs to be overwritten by the respective child-class.

        :param path_to_file_system: The path to where the file-system of the image has been stored.
        :returns: A list of tuples containing a dictionary, which represents the service manifest
                  for the software represented by the :class:`ConfigFileFinder` instance, and
                  a string representing the path where the discovered configuration files are
                  stored. If nothing was found, am empty list is returned.
        """

    @abstractmethod
    def check_call_command_in_container(
            self,
            path_to_file_system: str,
            docker_config: Dict
    ) -> List[Tuple[Dict, str]]:
        """
        This method is to be called if none of the other methods returned
        anything, and can be viewed as a last resort. Here, we are searching
        for call commands which may call the respective service, and try
        to extract it from there.

        This method is of heuristic nature.

        This needs to be overwritten by the respective child-class.

        :param path_to_file_system: The path to the folder where the file-system of the image
                                    is being stored.
        :param docker_config: The Docker configuration of the Docker image as returned by
                              `docker inspect`.
        :returns: A list of tuples containing a dictionary, which represents the service manifest
                  for the software represented by the :class:`ConfigFileFinder` instance, and
                  a string representing the path where the discovered configuration files are
                  stored. If nothing was found, am empty list is returned.
        """

    @abstractmethod
    def get_service_name(self) -> str:
        """
        The string representation of the service, so that we can categorize
        it in the final manifest file.

        :returns: The name of the service this class represents.
        """

    def find_configuration_files(self,
                                 path_to_file_system: str,
                                 docker_config: Dict) -> List[Tuple[Dict, str]]:
        """
        The main entrypoint for functions which are supposed to find
        configuration files within the extracted file system.

        The return value is supposed to be a list of tuples containing a dictionary,
        which represents a service portion from the manifest we expect in CoGuard,
        and a folder where the extracted configuration files are stored.

        Hence, a sample output would be:

        ```
        (
          {
            "version": "1.13.0",
            "serviceName": "nginx",
            "configFileList": [
              {
                "fileName": "nginx.conf",
                "defaultFileName": "nginx.conf",
                "subPath": ".",
                "configFileType": "nginx"
              }
            ]
          },
          "/tmp/my_temp_folder_with_config_files"
        )
        ```

        Where `/tmp/my_temp_folder_with_config_files` has the following contents

        ```
        ├── my_temp_folder_with_config_files
        │   └── nginx.conf
        ```

        The finding algorithm has three main methods, which represent the following
        strategies:

        1) Keep a database for each service of a “standard location” and look there first.

        2) If the configuration was not found in the standard location,
        do a search through the file-system for the respective
        file-names that the file is usually found under.

        3) If that does not yield anything, try to see if the services
        are installed, and then check if a custom configuration file
        has been defined in the call command. For that, the docker_config parameter
        is being used.

        :param path_to_file_system: The path to the folder where the file-system of the image
                                    is being stored.
        :param docker_config: The Docker configuration of the Docker image as returned by
                              `docker inspect`.
        """
        configuration_in_standard_location = self.check_for_config_files_in_standard_location(
            path_to_file_system
        )
        if configuration_in_standard_location is not None:
            return [configuration_in_standard_location]
        configuration_file_system_search = self.check_for_config_files_filesystem_search(
            path_to_file_system
        )
        heuristic_message = (
            f"{COLOR_YELLOW}Found configuration files for {self.get_service_name()}"
            " in non-standard location. "
            f"Keep in mind that this is a heuristic method.{COLOR_TERMINATION}"
        )
        if len(configuration_file_system_search) > 0:
            print(heuristic_message)
            return configuration_file_system_search
        configuration_using_executables = self.check_call_command_in_container(
            path_to_file_system,
            docker_config
        )
        if len(configuration_using_executables) > 0:
            print(heuristic_message)
        return configuration_using_executables

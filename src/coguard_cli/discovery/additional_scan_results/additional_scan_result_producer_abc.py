"""
This is an abstract base class capturing the results of external scanners and adding
them to the final results.
"""

import logging
from typing import Dict, Optional
import shutil
from abc import ABC, abstractmethod

class AdditionalScanResult(ABC):
    """
    This is an abstract class which collects results from external tooling
    and enriches the final report from CoGuard with these results.

    The main purpose of this class is to categorize these external-result-finders
    later and serve them via a factory abstraction.
    """

    @abstractmethod
    def perform_external_scan(
            self,
            path_to_file_system: str,
            additional_parameters: Optional[Dict]=None) -> Optional[str]:
        """
        The main function to perform the external scan function.
        It consumes a path where the external scanner needs to point at, and some additional
        optional parameters, if provided or necessary.
        This function is expected to create a temporary folder where the results of the
        additional scan is stored. It returns `None` if an error occurred.
        The output is meant to be forwarded to the `translate_external_scan_result` function
        for further processing. Any additional communication protocols between these functions
        needs to be captured in the classes inheriting from this abstract base class.
        """


    @abstractmethod
    def translate_external_scan_result(
            self,
            path_to_scan_result: str) -> Optional[str]:
        """
        This abstract function contains the functionality to translate the scan result
        produced by `perform_external_scan`, and create a new temporary folder where
        a JSON is stored with CoGuard compatible JSON objects which can be fed into a result.
        If an error occurs, this function returns None.
        """

    @abstractmethod
    def get_external_scan_identifier(self) -> str:
        """
        The string representation of the scan result.
        This is important for the later categorization.
        """

    def perform_external_scan_and_translation(
            self,
            path_to_filesystem: str,
            additional_parameters: Optional[Dict]) -> Optional[str]:
        """
        This is the main function to perform the external scans, produce the results
        and return the folder where the JSON is stored with the external scan result.
        It returns None if an error occurred.
        """
        if path_to_filesystem is None:
            logging.error(
                ("Unexpectedly, the folder where the filesystem was "
                 "located is None when trying to apply %s."),
                self.get_external_scan_identifier()
            )
            return None
        temp_results = self.perform_external_scan(path_to_filesystem, additional_parameters)
        if temp_results is None:
            logging.error("An error occurred while scanning with the external method for %s.",
                          self.get_external_scan_identifier())
            shutil.rmtree(temp_results)
            return None
        coguard_folder_result = self.translate_external_scan_result(temp_results)
        if coguard_folder_result is None:
            logging.error(
                "An error occurred while trying to translate the external scanner results."
            )
        shutil.rmtree(temp_results)
        return coguard_folder_result

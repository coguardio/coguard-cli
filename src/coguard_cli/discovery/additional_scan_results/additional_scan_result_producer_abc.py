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
        Executes an external scan on the given file system path using an external scanning tool.

        Parameters:
        path_to_file_system (str): The root path of the file system to be scanned.
        additional_parameters (Optional[Dict]): Optional parameters to customize the scan behavior.

        Returns:
        Optional[str]: The path to a temporary directory containing the scan results,
        or `None` if the scan failed.

        Notes:
        - This method must be implemented by subclasses.
        - The resulting output is expected to be passed to the `translate_external_scan_result`
          method for parsing and enrichment.
        - Any communication protocol or contract between this method and
          `translate_external_scan_result` must be defined and enforced by the subclass.
    """


    @abstractmethod
    def translate_external_scan_result(
            self,
            path_to_scan_result: str) -> Optional[str]:
        """
        Translates the raw results produced by `perform_external_scan` into a
        CoGuard-compatible format.

        Parameters:
        path_to_scan_result (str): Path to the directory containing the raw scan output.

        Returns:
        Optional[str]: Path to a temporary directory containing one or more
        CoGuard-compatible JSON files,
        or `None` if an error occurred during translation.

        Notes:
        - This method must be implemented by subclasses.
        - The translated results are expected to conform to CoGuard’s expected input format
          and can be consumed directly by CoGuard’s result processing pipeline.
        """

    @abstractmethod
    def get_external_scan_identifier(self) -> str:
        """
        Returns a unique string identifier for the type of external scan performed.

        Returns:
        str: A short, descriptive identifier used for categorizing and distinguishing
        the external scan results (e.g., the name of the external tool).

        Notes:
        - This identifier is used internally for organizing scan results and associating
         them with the correct translation logic.
        - Must be implemented by all subclasses.
        """

    def perform_external_scan_and_translation(
            self,
            path_to_filesystem: str,
            additional_parameters: Optional[Dict]) -> Optional[str]:
        """
        Orchestrates the full external scanning workflow: performs the scan and
        translates the results.

        Parameters:
        path_to_filesystem (str): Path to the file system to be scanned.
        additional_parameters (Optional[Dict]): Optional parameters passed to the external scanner.

        Returns:
        Optional[str]: Path to a temporary directory containing CoGuard-compatible JSON scan
        results, or `None` if an error occurred during scanning or translation.

        Notes:
        - This method coordinates both the scan execution and result translation.
        - Temporary scan artifacts are automatically cleaned up after translation.
        - Errors during either phase are logged and result in a `None` return value.
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
            return None
        coguard_folder_result = self.translate_external_scan_result(temp_results)
        if coguard_folder_result is None:
            logging.error(
                "An error occurred while trying to translate the external scanner results for %s.",
                self.get_external_scan_identifier()
            )
        shutil.rmtree(temp_results)
        return coguard_folder_result

"""
This module handles the external scans and production of the folders to
be communicated to the functions which zip up their results and upload them
to the CoGuard API.
"""
import logging
from typing import List, Dict, Optional
import coguard_cli.discovery.additional_scan_results.additional_scan_result_factory as fact

def perform_external_scans_and_return_folders(
        path_to_filesystem: str,
        additional_parameters: Optional[Dict],
        selected_additional_scanners: List[str]):
    """
    This is a function which executes all requested external scan on
    the path and returns a dict containing the scan identifier and
    folders where the results have been stored.
    """
    result = {}
    for add_scan_result in fact.additional_scan_result_factory():
        ext_scan_identifier = add_scan_result.get_external_scan_identifier()
        if ext_scan_identifier in selected_additional_scanners:
            if ext_scan_identifier in result:
                logging.error(
                    ("It appears that %s is already in the dictionary of "
                     "external scanners and will be overwritten."),
                    ext_scan_identifier
                )
            translation_success = add_scan_result.perform_external_scan_and_translation(
                path_to_filesystem,
                additional_parameters
            )
            if translation_success:
                result[ext_scan_identifier] = translation_success
    return result

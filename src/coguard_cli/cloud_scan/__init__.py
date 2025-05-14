"""
Helper functions for cloud provider scan functionality.
"""
import logging
import shutil
from typing import Optional

from coguard_cli.auth.enums import DealEnum
from coguard_cli.discovery.cloud_discovery.cloud_provider_factory import cloud_provider_factory
from coguard_cli.print_colors import COLOR_TERMINATION, \
    COLOR_CYAN, COLOR_YELLOW
from coguard_cli.auth.token import Token
from coguard_cli import folder_scan
from coguard_cli.auth.auth_config import CoGuardCliConfig
from coguard_cli.util import dry_run_outp, \
    upload_and_evaluate_zip_candidate

def perform_cloud_provider_scan(
        cloud_provider_name: Optional[str],
        credentials_file: Optional[str],
        deal_type: DealEnum,
        auth_config: CoGuardCliConfig,
        token: Token,
        organization: str,
        coguard_api_url: Optional[str],
        output_format: str,
        fail_level: int,
        ruleset: str,
        dry_run: bool = False):
    """
    Helper function to run a scan on a folder. If the folder_name parameter is None,
    the current working directory is being used.
    """
    provider_name = cloud_provider_name or "aws"
    print(f"{COLOR_CYAN}SCANNING CLOUD_PROVIDER {COLOR_TERMINATION}{provider_name}")
    cloud_provider = None
    for cloud_provider in cloud_provider_factory():
        logging.debug("Checking if %s matches.", cloud_provider.get_cloud_provider_name())
        if cloud_provider.get_cloud_provider_name() == provider_name:
            break
    if not cloud_provider or cloud_provider.get_cloud_provider_name() != provider_name:
        logging.error("The cloud provider you requested is not implemented yet.")
        return
    folder_name = cloud_provider.extract_iac_files_for_account(
        auth_config,
        credentials_file
    )
    if not folder_name:
        logging.error("Unable to extract the requested cloud provider %s.",
                      provider_name)
        return
    collected_config_file_tuple = folder_scan.find_configuration_files_and_collect(
        folder_name,
        organization or auth_config.get_username(),
        f"{provider_name}_extraction"
    )
    zip_candidate = folder_scan.create_zip_to_upload_from_file_system(
        collected_config_file_tuple
    )
    collected_location, _ = collected_config_file_tuple
    shutil.rmtree(collected_location, ignore_errors=True)
    shutil.rmtree(folder_name)
    if zip_candidate is None:
        print(f"{COLOR_YELLOW}Cloud Provider {provider_name} - NO CONFIGURATION FILES FOUND.")
        return
    if dry_run:
        dry_run_outp(zip_candidate)
    else:
        upload_and_evaluate_zip_candidate(
            zip_candidate,
            auth_config,
            deal_type,
            token,
            coguard_api_url,
            f"{provider_name}_extraction",
            output_format,
            fail_level,
            organization,
            ruleset
        )

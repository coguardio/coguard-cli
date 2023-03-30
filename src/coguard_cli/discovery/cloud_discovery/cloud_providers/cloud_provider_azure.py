"""
This module contains the class to represent the AZURE cloud provider, and the necessary functions.
"""

import logging
from pathlib import Path
from typing import Optional, Dict
import tempfile
from coguard_cli.discovery.cloud_discovery.cloud_provider_abc import CloudProvider
from coguard_cli import docker_dao
from coguard_cli.auth.auth_config import CoGuardCliConfig

class CloudProviderAzure(CloudProvider):
    """
    The class to represent AZURE as a cloud provider.
    """

    def get_cloud_provider_name(self) -> str:
        """
        Overriding the abstract base class function.
        """
        return "azure"

    def extract_credentials(self,
                            credentials_file: Optional[str] = None) -> Optional[Dict]:
        """
        Overriding the abstract base class function.
        """
        azure_conf_path = Path(Path.home(), ".azure")
        if not azure_conf_path.exists():
            return None
        return {
            "conf_path": azure_conf_path
        }

    def extract_iac_files_for_account(self,
                                      cli_config: CoGuardCliConfig,
                                      credentials_file: Optional[str] = None) -> Optional[str]:
        """
        Consider the abstract base class for documentation.
        """
        extracted_credentials = self.extract_credentials()
        if not extracted_credentials:
            logging.info("Could not extract the credentials for Azure.")
            return None
        temp_location = tempfile.mkdtemp(prefix="azure_cloud_extraction")
        environment_variables = {
            "PROVIDER": self.get_cloud_provider_name()
        }
        mounts = [(extracted_credentials["conf_path"], "/home/terraformerUser/.azure")]
        res = docker_dao.terraformer_wrapper(
            temp_location,
            environment_variables,
            mounts,
            self.get_cloud_provider_name(),
            "google")
        if not res:
            return None
        return temp_location

CloudProvider.register(CloudProviderAzure)

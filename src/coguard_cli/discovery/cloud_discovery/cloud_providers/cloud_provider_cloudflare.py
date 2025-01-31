"""
This module contains the class to represent the Cloudflare cloud provider, and the necessary functions.
"""

import logging
import json
from typing import Optional, Dict
import tempfile
from coguard_cli.discovery.cloud_discovery.cloud_provider_abc import CloudProvider
from coguard_cli import docker_dao
from coguard_cli.auth.auth_config import CoGuardCliConfig

class CloudProviderCloudflare(CloudProvider):
    """
    The class to represent Cloudflare as a cloud provider.
    """

    def __init__(self):
        """
        The initialization function.
        """
        self._api_token = ""
        self._account_id = ""

    def get_cloud_provider_name(self) -> str:
        """
        Overriding the abstract base class function.
        """
        return "cloudflare"

    def extract_credentials(self,
                            credentials_file: Optional[str] = None) -> Optional[Dict]:
        """
        Overriding the abstract base class function.
        """
        if credentials_file:
            with open(credentials_file, 'r', encoding='utf-8') as auth_json:
                result = json.load(auth_json)
                self._api_token = result.get("apiKey", "")
                self._account_id = result.get("accountId")
            return None if (not self._api_token or not self._account_id) else result
        logging.error(
            "Cloudflare's credentials need to be communicated via a credentials file. "
            "That file is a json, with the keys `apiKey` and `accountId`."
        )
        return None

    def extract_iac_files_for_account(self,
                                      cli_config: CoGuardCliConfig,
                                      credentials_file: Optional[str] = None) -> Optional[str]:
        """
        Consider the abstract base class for documentation.
        """
        extracted_credentials = self.extract_credentials(credentials_file)
        if not extracted_credentials:
            logging.info("Could not extract the credentials for Cloudflare.")
            return None
        temp_location = tempfile.mkdtemp(prefix="cloudflare_cloud_extraction")
        environment_variables = {
            "PROVIDER": self.get_cloud_provider_name(),
            "CLOUDFLARE_API_TOKEN": self._api_token,
            "CLOUDFLARE_ACCOUNT_ID": self._account_id
        }
        res = docker_dao.terraformer_wrapper(
            temp_location,
            environment_variables,
            [],
            self.get_cloud_provider_name(),
            "cloudflare")
        if not res:
            return None
        return temp_location

CloudProvider.register(CloudProviderCloudflare)

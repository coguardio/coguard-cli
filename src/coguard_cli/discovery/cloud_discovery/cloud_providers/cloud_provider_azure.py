"""
This module contains the class to represent the AZURE cloud provider, and the necessary functions.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict
import tempfile
from coguard_cli.discovery.cloud_discovery.cloud_provider_abc import CloudProvider
from coguard_cli import docker_dao
from coguard_cli.auth.auth_config import CoGuardCliConfig

_SP_JSON_TO_ENV = {
    "clientId": "ARM_CLIENT_ID",
    "clientSecret": "ARM_CLIENT_SECRET",
    "tenantId": "ARM_TENANT_ID",
    "subscriptionId": "ARM_SUBSCRIPTION_ID"
}

class CloudProviderAzure(CloudProvider):
    """
    The class to represent AZURE as a cloud provider.
    """

    def get_cloud_provider_name(self) -> str:
        """
        Overriding the abstract base class function.
        """
        return "azure"

    def _extract_from_credentials_file(self, credentials_file: str) -> Optional[Dict]:
        """
        Reads Azure service principal credentials from a JSON file.
        Expected keys: clientId, clientSecret, tenantId, subscriptionId.
        """
        try:
            with open(credentials_file, 'r', encoding='utf-8') as cred_json:
                creds = json.load(cred_json)
            missing = [k for k in _SP_JSON_TO_ENV if k not in creds]
            if missing:
                logging.error("Azure credentials file missing required keys: %s",
                              ", ".join(missing))
                return None
            result = {"auth_mode": "service_principal"}
            for json_key, env_var in _SP_JSON_TO_ENV.items():
                result[env_var] = creds[json_key]
            return result
        except (json.JSONDecodeError, OSError) as err:
            logging.error("Failed to read Azure credentials file: %s", err)
            return None

    def _extract_from_environment(self) -> Optional[Dict]:
        """
        Reads Azure service principal credentials from environment variables.
        """
        env_vars = _SP_JSON_TO_ENV.values()
        values = {var: os.environ.get(var, "") for var in env_vars}
        if all(values.values()):
            return {"auth_mode": "service_principal", **values}
        return None

    def _extract_from_az_cli(self) -> Optional[Dict]:
        """
        Falls back to the local ~/.azure directory for az CLI auth.
        """
        azure_conf_path = Path(Path.home(), ".azure")
        if not azure_conf_path.exists():
            return None
        return {
            "auth_mode": "cli",
            "conf_path": azure_conf_path
        }

    def extract_credentials(self,
                            credentials_file: Optional[str] = None) -> Optional[Dict]:
        """
        Overriding the abstract base class function.

        Tries three sources in order:
        1. A JSON credentials file (if provided)
        2. Environment variables (ARM_CLIENT_ID, ARM_CLIENT_SECRET,
           ARM_TENANT_ID, ARM_SUBSCRIPTION_ID)
        3. Local ~/.azure directory (az CLI login)
        """
        if credentials_file:
            return self._extract_from_credentials_file(credentials_file)
        env_creds = self._extract_from_environment()
        if env_creds:
            return env_creds
        return self._extract_from_az_cli()

    def extract_iac_files_for_account(self,
                                      cli_config: CoGuardCliConfig,
                                      credentials_file: Optional[str] = None) -> Optional[str]:
        """
        Consider the abstract base class for documentation.
        """
        extracted_credentials = self.extract_credentials(credentials_file)
        if not extracted_credentials:
            logging.info("Could not extract the credentials for Azure.")
            return None
        temp_location = tempfile.mkdtemp(prefix="azure_cloud_extraction")
        environment_variables = {
            "PROVIDER": self.get_cloud_provider_name()
        }
        mounts = []
        if extracted_credentials["auth_mode"] == "service_principal":
            for var in _SP_JSON_TO_ENV.values():
                environment_variables[var] = extracted_credentials[var]
        else:
            mounts.append(
                (extracted_credentials["conf_path"], "/home/terraformerUser/.azure")
            )
        res = docker_dao.terraformer_wrapper(
            temp_location,
            environment_variables,
            mounts,
            self.get_cloud_provider_name(),
            "azure")
        if not res:
            return None
        return temp_location

CloudProvider.register(CloudProviderAzure)

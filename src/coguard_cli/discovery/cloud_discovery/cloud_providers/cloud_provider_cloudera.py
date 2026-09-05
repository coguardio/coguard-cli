"""
This module contains the class to represent Cloudera as a "cloud provider" for
the purpose of the `coguard cloud cloudera` sub-command.

In contrast to the hyperscaler providers, Cloudera is not exported as
Infrastructure as Code. Instead, the running deployment is inspected through the
Cloudera Manager API, and its services, roles and generated configuration files
are turned directly into a CoGuard cluster representation.
"""

import getpass
import json
import logging
import os
import sys
from typing import Dict, Optional, Tuple

import yaml

from coguard_cli.auth.auth_config import CoGuardCliConfig
from coguard_cli.discovery.cloud_discovery.cloud_provider_abc import CloudProvider
from coguard_cli.discovery.cloudera_discovery import \
    extract_cloudera_cluster_representation
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi, ClouderaManagerApiError
from coguard_cli.print_colors import COLOR_RED, COLOR_TERMINATION

# Environment variables which are consulted if the respective value was neither
# passed on the command line nor found in a credentials file.
ENVIRONMENT_VARIABLES = {
    "url": "CLOUDERA_MANAGER_URL",
    "username": "CLOUDERA_MANAGER_USER",
    "password": "CLOUDERA_MANAGER_PASSWORD",
    "ca_cert": "CLOUDERA_MANAGER_CA_CERT",
    "verify_tls": "CLOUDERA_MANAGER_VERIFY_TLS",
    "cluster": "CLOUDERA_CLUSTER",
}

FALSE_STRINGS = frozenset(["0", "false", "no", "off"])


class CloudProviderCloudera(CloudProvider):
    """
    The class to represent a Cloudera deployment, inspected through the
    Cloudera Manager API.
    """

    def __init__(self, options: Optional[Dict] = None):
        """
        The initialization function. The `options` dictionary carries the
        Cloudera Manager connection parameters as provided on the command line.
        """
        self._options = options or {}

    def get_cloud_provider_name(self) -> str:
        """
        Overriding the abstract base class function.
        """
        return "cloudera"

    def set_options(self, options: Optional[Dict]) -> None:
        """
        Sets the connection options. This is used by the factory-instantiated
        instance, which cannot receive constructor arguments.
        """
        self._options = options or {}

    @staticmethod
    def _load_credentials_file(credentials_file: str) -> Dict:
        """
        Loads a JSON or YAML credentials file. An empty dictionary is returned
        if it could not be parsed.
        """
        try:
            with open(credentials_file, 'r', encoding='utf-8') as file_stream:
                content = file_stream.read()
        except OSError as err:
            logging.error("Could not read the credentials file %s: %s",
                          credentials_file,
                          err)
            return {}
        try:
            return json.loads(content) or {}
        except json.JSONDecodeError:
            logging.debug("%s is not JSON. Attempting to parse it as YAML.",
                          credentials_file)
        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as err:
            logging.error("Could not parse the credentials file %s: %s",
                          credentials_file,
                          err)
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def extract_credentials(self,
                            credentials_file: Optional[str] = None) -> Optional[Dict]:
        """
        Overriding the abstract base class function.

        The Cloudera Manager connection parameters are resolved with the
        following precedence: command line options, credentials file,
        environment variables. A missing password is prompted for
        interactively, provided the session is attached to a terminal.
        """
        from_file = self._load_credentials_file(credentials_file) \
            if credentials_file else {}
        result = {}
        for key, environment_variable in ENVIRONMENT_VARIABLES.items():
            value = self._options.get(key)
            if value is None:
                value = from_file.get(key)
            if value is None:
                value = os.environ.get(environment_variable)
            if value is not None:
                result[key] = value
        if not result.get("url"):
            logging.error(
                "No Cloudera Manager URL provided. Please pass "
                "`--cloudera-manager-url`, or set the %s environment variable.",
                ENVIRONMENT_VARIABLES["url"]
            )
            return None
        if not result.get("username"):
            logging.error(
                "No Cloudera Manager user provided. Please pass "
                "`--cloudera-manager-user`, or set the %s environment variable.",
                ENVIRONMENT_VARIABLES["username"]
            )
            return None
        if not result.get("password"):
            if not sys.stdin.isatty():
                logging.error(
                    "No Cloudera Manager password provided. Please set the %s "
                    "environment variable.",
                    ENVIRONMENT_VARIABLES["password"]
                )
                return None
            result["password"] = getpass.getpass(
                f"Password for Cloudera Manager user {result['username']}: "
            )
            if not result["password"]:
                return None
        # TLS verification is on unless it was explicitly switched off.
        verify_tls = result.get("verify_tls", True)
        if isinstance(verify_tls, str):
            verify_tls = verify_tls.strip().lower() not in FALSE_STRINGS
        result["verify_tls"] = bool(verify_tls)
        return result

    def extract_iac_files_for_account(
            self,
            cli_config: CoGuardCliConfig,
            credentials_file: Optional[str] = None) -> Optional[str]:
        """
        Overriding the abstract base class function.

        Cloudera is not exported as Infrastructure as Code. The cluster
        representation is produced by `extract_cluster_representation` instead.
        """
        logging.debug(
            "Cloudera does not support an Infrastructure as Code export. "
            "The cluster representation is extracted from the Cloudera "
            "Manager API instead."
        )

    def extract_cluster_representation(
            self,
            cli_config: CoGuardCliConfig,
            credentials_file: Optional[str] = None,
            customer_id: Optional[str] = None) -> Optional[Tuple[str, Dict]]:
        """
        Overriding the base class function.

        Queries the Cloudera Manager API and produces a CoGuard infrastructure
        description folder together with its manifest.
        """
        credentials = self.extract_credentials(credentials_file)
        if not credentials:
            return None
        try:
            api = ClouderaManagerApi(
                base_url=credentials["url"],
                username=credentials["username"],
                password=credentials["password"],
                verify_tls=credentials["verify_tls"],
                ca_cert=credentials.get("ca_cert")
            )
        except ClouderaManagerApiError as err:
            print(f"{COLOR_RED}{err}{COLOR_TERMINATION}")
            return None
        if not api.check_connection():
            print(f"{COLOR_RED}Could not connect to Cloudera Manager at "
                  f"{credentials['url']}. Please verify the URL, the "
                  f"credentials, and whether the certificate needs to be "
                  f"trusted via `--cloudera-manager-ca-cert` or TLS "
                  f"verification disabled via "
                  f"`--cloudera-manager-no-verify-tls`.{COLOR_TERMINATION}")
            return None
        return extract_cloudera_cluster_representation(
            api,
            customer_id or cli_config.get_username(),
            credentials.get("cluster")
        )

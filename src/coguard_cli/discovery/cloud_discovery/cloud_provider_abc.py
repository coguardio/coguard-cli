"""
This module contains the abstract base class to specify a cloud provider
and have some basic functions defined.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from coguard_cli.auth.auth_config import CoGuardCliConfig

class CloudProvider(ABC):
    """
    This is an abstract base class for a cloud provider, together with
    some common abstract functionality.
    """

    @abstractmethod
    def get_cloud_provider_name(self) -> str:
        """
        This function must be implemented and return the name of the cloud provider
        considered in the specific child-class.
        """

    @abstractmethod
    def extract_credentials(self,
                            credentials_file: Optional[str] = None) -> Optional[Dict]:
        """
        The implementation of the function to get the credentials and return
        them as a dictionary. If no credentials could be extracted, None is being returned.
        """

    @abstractmethod
    def extract_iac_files_for_account(
            self,
            cli_config: CoGuardCliConfig,
            credentials_file: Optional[str] = None) -> Optional[str]:
        """
        The main function which creates a temporary folder,
        and then extracts all cloud information in IaC. If the process
        succeeded, a folder-name is returned where the files can be found.

        If the process failed, None is returned.
        """

    # pylint: disable=unused-argument
    def extract_cluster_representation(
            self,
            cli_config: CoGuardCliConfig,
            credentials_file: Optional[str] = None,
            customer_id: Optional[str] = None) -> Optional[Tuple[str, Dict]]:
        """
        Optional counterpart to :func:`extract_iac_files_for_account` for
        providers which are able to produce a CoGuard infrastructure
        description, i.e. a folder and its manifest, directly.

        This is the case for providers whose API already exposes a cluster of
        services with their configuration files, so that the auto-discovery of
        configuration files inside an Infrastructure as Code export would only
        lose information.

        Providers which do not support this return `None`, which is the default,
        and are then processed through the Infrastructure as Code path.
        """
        return None

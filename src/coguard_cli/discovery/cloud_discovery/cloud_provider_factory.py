"""
This module contains a factory to produce the cloud provider
instances needed to consider.
"""

from typing import Generator

# pylint: disable=unused-import
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_aws \
    import CloudProviderAWS
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_gcp \
    import CloudProviderGCP
from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_azure \
    import CloudProviderAzure
from coguard_cli.discovery.cloud_discovery.cloud_provider_abc import CloudProvider

def cloud_provider_factory() -> Generator[CloudProvider, None, None]:
    """
    The factory to get different instances to repesent cloud providers.
    """
    for cls in CloudProvider.__subclasses__():
        yield cls()

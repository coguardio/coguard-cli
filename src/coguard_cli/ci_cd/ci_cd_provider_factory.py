"""
This module contains a factory to produce CI/CD provider instances.
"""

from typing import Generator

# pylint: disable=unused-import
from coguard_cli.ci_cd.ci_cd_providers.ci_cd_provider_github import CiCdProviderGitHub
from coguard_cli.ci_cd.ci_cd_provider_abc import CiCdProvider

def ci_cd_provider_factory() -> Generator[CiCdProvider, None, None]:
    """
    The factory to get different instances of CI/CD providers
    """
    for cls in CiCdProvider.__subclasses__():
        yield cls()

"""
This module contains the CI/CD provider representation for GitHub Actions.
"""

from pathlib import Path
from typing import Optional
from coguard_cli.ci_cd.ci_cd_provider_abc import CiCdProvider
from coguard_cli.util import CiCdProviderNames
from coguard_cli.print_colors import COLOR_TERMINATION, \
    COLOR_RED, COLOR_YELLOW, COLOR_CYAN

class CiCdProviderGitHub(CiCdProvider):
    """
    The class to represent GitHub as a CI/CD provider.
    """

    def add(self, location: str) -> Optional[str]:
        """
        Generates the subfolders and the CI/CD file.
        """
        working_dir_of_this_file = Path(__file__).resolve().parent
        location_path = Path(location)
        ci_cd_path = location_path.joinpath('.github', 'workflows')
        ci_cd_path.mkdir(parents=True, exist_ok=True)
        src_file = working_dir_of_this_file.parent.joinpath(
            'ci_cd_scripts',
            'github',
            'github_coguard_action.yml'
        )
        dest_file = ci_cd_path.joinpath('coguard_scan.yml')
        if dest_file.exists():
            print(f"{COLOR_RED}The actions script already exist. Exiting.{COLOR_TERMINATION}")
            return None
        dest_file.write_bytes(src_file.read_bytes())
        print(f"{COLOR_CYAN}Created GitHub actions file {dest_file}{COLOR_TERMINATION}")
        return str(ci_cd_path)

    def post_string(self) -> str:
        """
        Reminds people right now that they need to create secrets.
        """
        return f"""{COLOR_YELLOW}
        The GitHub Actions script contains two references to GitHub secrets:
         - `secrets.COGUARD_USER_NAME`
         - `secrets.COGUARD_PASSWORD`
        You need to sign up for CoGuard, and then create these secrets
        in GitHub for the CI/CD script to work.
        Instructions on how to set up GitHub secrets can be found here:
        https://docs.github.com/en/actions/security-guides/encrypted-secrets
        {COLOR_TERMINATION}""".replace("        ", "")

    def get_identifier(self) -> str:
        """
        The identifier of this CI/CD provider.
        """
        return CiCdProviderNames.GITHUB.value

CiCdProvider.register(CiCdProviderGitHub)

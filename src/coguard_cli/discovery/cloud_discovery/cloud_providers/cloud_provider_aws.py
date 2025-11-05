"""
This module contains the class to represent the AWS cloud provider, and the necessary functions.
"""

import logging
from typing import Optional, Dict, List
import tempfile
import boto3
from coguard_cli.discovery.cloud_discovery.cloud_provider_abc import CloudProvider
from coguard_cli import docker_dao
from coguard_cli.auth.auth_config import CoGuardCliConfig

class CloudProviderAWS(CloudProvider):
    """
    The class to represent AWS as a cloud provider.
    """

    def __init__(self,
                 aws_access_key_id: str = "",
                 aws_secret_access_key: str = ""):
        """
        The initialization function.
        """
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key

    def get_cloud_provider_name(self) -> str:
        """
        Overriding the abstract base class function.
        """
        return "aws"

    def _get_profile(self, profile_names: List[str]) -> str:
        """
        The prompt to let the user enter the profile intended to
        be used, assuming that there are multiple profiles to
        choose from.
        """
        assert len(profile_names) > 1, \
            "This function should only be called with a list containing more than 1 element."
        print("Multiple profiles detected: " + "\n".join(profile_names))
        inp = ""
        while inp not in profile_names:
            inp = input(f"Please type the profile you wish to use (default: {profile_names[0]})")
            if not inp.strip():
                inp = profile_names[0]
            if inp not in profile_names:
                print("You typed an invalid profile name.")
        return inp


    def extract_credentials(self,
                            credentials_file: Optional[str] = None) -> Optional[Dict]:
        """
        Overriding the abstract base class function.
        """
        if self._aws_access_key_id and self._aws_secret_access_key:
            return {
                "aws_access_key_id": self._aws_access_key_id,
                "aws_secret_access_key": self._aws_secret_access_key
            }
        session = boto3.Session()
        profiles = session.available_profiles
        try:
            if len(profiles) == 0:
                logging.info("No profiles found.")
                credentials = session.get_credentials()
                if not credentials:
                    return None
            elif len(profiles) == 1:
                credentials = session.get_credentials()
            else:
                # The case of multiple profiles
                logging.debug("Multiple profiles given. Choosing one")
                profile = self._get_profile(profiles)
                logging.debug("Profile chosen: %s", profile)
                session = boto3.Session(profile_name=profile)
                credentials = session.get_credentials()
            self._aws_access_key_id = credentials.access_key
            self._aws_secret_access_key = credentials.secret_key
            return {
                "aws_access_key_id": credentials.access_key,
                "aws_secret_access_key": credentials.secret_key
            }
        #pylint: disable=broad-exception-caught
        except Exception as err:
            logging.error("Error while trying to retrieve access credentials: %s",
                          err)
            return None

    def extract_iac_files_for_account(self,
                                      cli_config: CoGuardCliConfig,
                                      credentials_file: Optional[str] = None) -> Optional[str]:
        """
        Consider the abstract base class for documentation.
        """
        extracted_credentials = self.extract_credentials()
        if not extracted_credentials:
            logging.info("Could not extract the credentials for AWS.")
            return None
        temp_location = tempfile.mkdtemp(prefix="aws_cloud_extraction")
        all_regions = self.get_all_regions()
        environment_variables = {
            "PROVIDER": self.get_cloud_provider_name(),
            "AWS_ACCESS_KEY_ID": self._aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": self._aws_secret_access_key,
            "REGIONS": ",".join(all_regions)
        }
        res = docker_dao.terraformer_wrapper(
            temp_location,
            environment_variables,
            [],
            self.get_cloud_provider_name(),
            self.get_cloud_provider_name()
        )
        if not res:
            return None
        return temp_location


    def get_all_regions(self):
        """
        Helper function to retrieve all regions.
        """
        default = [
            "us-east-2",
            "us-east-1",
            "us-west-1",
            "us-west-2",
            "af-south-1",
            "ap-east-1",
            "ap-south-2",
            "ap-southeast-3",
            "ap-southeast-4",
            "ap-south-1",
            "ap-northeast-3",
            "ap-northeast-2",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
            "ca-central-1",
            "eu-central-1",
            "eu-west-1",
            "eu-west-2",
            "eu-south-1",
            "eu-west-3",
            "eu-south-2",
            "eu-north-1",
            "eu-central-2",
            "me-south-1",
            "me-central-1",
            "sa-east-1"
        ]
        try:
            client = boto3.client("ec2")
            regions = [region['RegionName'] for region in client.describe_regions()['Regions']]
            return regions
        #pylint: disable=bare-except
        except:
            logging.debug("Could not extract activated regions. Using default")
        return default

CloudProvider.register(CloudProviderAWS)

"""
The main function is hosted here, and it will be the entrypoint for the command line
interface
"""

import argparse
import logging
import pkg_resources
from coguard_cli import entrypoint, SubParserNames, validate_output_format
from coguard_cli.util import CiCdProviderNames
from coguard_cli.auth.auth_config import DEFAULT_AUTH_URL, DEFAULT_COGUARD_URL

def set_logging_config(level):
    """
    Sets the chosen logging level, depending on the argument provided.

    :param level: The logging level.
    :type level: ("DEBUG"|"INFO"|"WARNING"|"ERROR"|"CRITICAL")
    """
    coguard_logging_format = '%(asctime)-12s [%(levelname)s] %(message)s'
    if level == "DEBUG":
        logging.basicConfig(
            format=coguard_logging_format,
            level=logging.DEBUG
        )
    elif level == "INFO":
        logging.basicConfig(
            format=coguard_logging_format,
            level=logging.INFO
        )
    elif level == "WARNING":
        logging.basicConfig(
            format=coguard_logging_format,
            level=logging.WARNING
        )
    elif level == "ERROR":
        logging.basicConfig(
            format=coguard_logging_format,
            level=logging.ERROR
        )
    elif level == "CRITICAL":
        logging.basicConfig(
            format=coguard_logging_format,
            level=logging.CRITICAL
        )
    else:
        raise ValueError("Log level needs to be one of "
                         "`DEBUG`,`INFO`,`WARNING`,`ERROR`, or `CRITICAL`")

def main():
    """
    The main entrypoint where the argument parsing is happening.
    """
    parser = argparse.ArgumentParser(description="The main entrypoint for CoGuard")
    parser.add_argument(
        '--coguard-api-url',
        type=str,
        dest='coguard_api_url',
        default=DEFAULT_COGUARD_URL,
        help='The url of the coguard api to call',
    )
    parser.add_argument(
        '--coguard-auth-url',
        type=str,
        dest='coguard_auth_url',
        default=DEFAULT_AUTH_URL,
        help='The url of the authentication server',
    )
    parser.add_argument(
        '--logging-level',
        type=str,
        dest='logging_level',
        default='INFO',
        help=("The logging level of this call. Can be one of the following: "
              "DEBUG, INFO, WARNING, ERRROR, CRITICAL")
    )
    parser.add_argument(
        '--minimum-fail-level',
        type=int,
        dest='fail_level',
        default='1',
        help=("The minimum severity level of failed checks for this program "
              "to not give a non-zero exit code.")
    )
    parser.add_argument(
        '--dry-run',
        type=bool,
        dest='dry_run',
        default=False,
        help=("When set to `true`, the CLI will generate a .zip file, but "
              "not upload it to the back-end for scanning/fixing.")
    )
    parser.add_argument(
        '--output-format',
        type=validate_output_format,
        dest='output_format',
        default='formatted',
        help=("The format of the output. It is either `formatted` (default), "
              "i.e. human readable to stdout, or it can be exported to other formats. "
              "Multiple formats can be chosen and concatenated via a comma.")
    )
    parser.add_argument(
        '--ruleset',
        type=str,
        dest='ruleset',
        choices=["soc2", "hipaa", "stig", ""],
        default='',
        help=("The non-default rule-set to use.")
    )
    parser.add_argument(
        '--additional-scan-result',
        action='append',
        choices=["trivy_cve_scan", "phpstan_sast_scan", ""],
        default=[],
        help='Additional scan result files or identifiers',
        dest='additional_scan_results'
    )
    subparsers = parser.add_subparsers(
        required=True,
        #Do not remove the next line. This is a workaround for https://bugs.python.org/issue29298
        dest='subparsers_location'
    )
    docker_image_parser = subparsers.add_parser(
        SubParserNames.DOCKER_IMAGE.value,
        help="The sub-command to scan a Docker image",
    )
    docker_image_parser.add_argument(
        'scan',
        type=str,
        default="",
        nargs='?',
        help=("The indicator that we are aiming to do a scan.")
    )
    docker_image_parser.add_argument(
        'image_name',
        metavar="image_name",
        type=str,
        default="",
        nargs='?',
        help=("The name/id of the image. Defaults to empty string, "
              "which means all images are being scanned.")
    )
    docker_container_parser = subparsers.add_parser(
        SubParserNames.DOCKER_CONTAINER.value,
        help="The sub-command to scan a Docker container",
    )
    docker_container_parser.add_argument(
        'scan',
        type=str,
        default="",
        nargs='?',
        help=("The indicator that we are aiming to do a scan.")
    )
    docker_container_parser.add_argument(
        'container_name',
        metavar="container_name",
        type=str,
        default="",
        nargs='?',
        help=("The name/id of the container. Defaults to empty string, "
              "which means all images are being scanned.")
    )
    folder_scanning_parser = subparsers.add_parser(
        SubParserNames.FOLDER_SCAN.value,
        help="The sub-command to find configuration files within a folder and scan them."
    )
    folder_scanning_parser.add_argument(
        "--fix",
        type=bool,
        dest='fix_flag',
        default=False,
        required=False,
        help="Upload the configuration files inside this folder and retrieve a fixed version."
    )
    folder_scanning_parser.add_argument(
        SubParserNames.SCAN.value,
        type=str,
        default="",
        nargs='?',
        help=("The indicator that we are aiming to do a scan.")
    )
    folder_scanning_parser.add_argument(
        'folder_name',
        metavar="folder_name",
        type=str,
        default="",
        nargs='?',
        help=("The path to the folder. Defaults to the current working directory.")
    )
    repo_scanning_parser = subparsers.add_parser(
        SubParserNames.REPO_SCAN.value,
        help="The sub-command to download a repository and scan configuration files within it."
    )
    repo_scanning_parser.add_argument(
        SubParserNames.SCAN.value,
        type=str,
        default="",
        nargs='?',
        help=("The indicator that we are aiming to do a scan.")
    )
    repo_scanning_parser.add_argument(
        'repo_url',
        metavar="repo_url",
        type=str,
        default="",
        nargs='?',
        help=("The url of the repository.")
    )
    open_api_endpoint_parser = subparsers.add_parser(
        SubParserNames.OPEN_API_SCAN.value,
        help="The sub-command to download an OpenAPI spec and scan it directly."
    )
    open_api_endpoint_parser.add_argument(
        SubParserNames.SCAN.value,
        type=str,
        default="",
        nargs='?',
        help=("The indicator that we are aiming to do a scan.")
    )
    open_api_endpoint_parser.add_argument(
        'open_api_url',
        metavar="open_api_url",
        type=str,
        default="",
        nargs='?',
        help=("The url to the OpenAPI JSON.")
    )
    cloud_scanning_parser = subparsers.add_parser(
        SubParserNames.CLOUD_SCAN.value,
        help="The sub-command to extract a cloud snapshot as Terraform files and scan them."
    )
    cloud_scanning_parser.add_argument(
        SubParserNames.SCAN.value,
        type=str,
        choices=["aws", "gcp", "azure", "scan", ""],
        default="",
        nargs='?',
        help=("The indicator that we are aiming to do a scan.")
    )
    cloud_scanning_parser.add_argument(
        'cloud_provider_name',
        metavar="cloud_provider_name",
        choices=["aws", "gcp", "azure", ""],
        type=str,
        default="",
        nargs='?',
        help=("The name of the cloud providers. The choices are \"gcp\", "
              "\"aws\" and \"azure\". Defaults to \"aws.\"")
    )
    cloud_scanning_parser.add_argument(
        '--credentials-file',
        type=str,
        dest='credentials_file',
        required=False,
        help=("A credentials file, if it is available.")
    )
    ci_cd_parser = subparsers.add_parser(
        SubParserNames.CI_CD_GEN.value,
        help="The sub-command to generate CI-CD-files to add to your pipeline."
    )
    ci_cd_parser.add_argument(
        'ci_cd_provider_name',
        metavar="ci_cd_provider_name",
        type=str,
        choices=[ci_cd_provider.value for ci_cd_provider in CiCdProviderNames],
        nargs='?',
        help=("The name of the CI/CD provider.")
    )
    ci_cd_parser.add_argument(
        'ci_cd_command',
        metavar="ci_cd_command",
        type=str,
        choices=["add"],
        nargs='?',
        help=("The action you would like to take.")
    )
    ci_cd_parser.add_argument(
        'repository_folder',
        metavar="repository_folder",
        default=".",
        type=str,
        nargs='?',
        help=("The action you would like to take.")
    )
    account_parser = subparsers.add_parser(
        SubParserNames.ACCOUNT.value,
        help="The sub-command to obtain account information."
    )
    account_parser.add_argument(
        'account_action',
        metavar="account_action",
        default="download-cluster-report",
        choices=["download-cluster-report"],
        type=str,
        nargs='?',
        help=("The account action you would like to perform.")
    )
    account_parser.add_argument(
        'cluster_name',
        metavar="cluster_name",
        type=str,
        nargs='?',
        help=("The cluster name.")
    )
    account_parser.add_argument(
        'download_location',
        metavar="download_location",
        type=str,
        default='',
        nargs='?',
        help=("The download location.")
    )
    subparsers.add_parser(
        SubParserNames.SCAN.value,
        help="The sub-command to scan everything, using default parameters.",
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=pkg_resources.get_distribution("coguard-cli").version
    )
    args = parser.parse_args()
    set_logging_config(args.logging_level)
    entrypoint(args)

if __name__ == '__main__':
    main()

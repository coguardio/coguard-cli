"""
The CoGuard CLI top level entrypoint where the entrypoint function is being defined
"""

from enum import Enum
import argparse
import shutil
import os
import sys
import logging
import tempfile
import subprocess
import urllib.request
import pathlib
from pathlib import Path
from typing import Optional
from coguard_cli import image_check
from coguard_cli import folder_scan
from coguard_cli import cloud_scan
from coguard_cli.check_common_util import replace_special_chars_with_underscore
from coguard_cli.ci_cd.ci_cd_provider_factory import ci_cd_provider_factory
from coguard_cli.auth.auth_config import CoGuardCliConfig
from coguard_cli.auth.token import Token
import coguard_cli.auth.util
from coguard_cli.auth.enums import DealEnum
import coguard_cli.api_connection
from coguard_cli.print_colors import COLOR_TERMINATION, \
    COLOR_RED, COLOR_YELLOW

class SubParserNames(Enum):
    """
    The enumeration capturing the different supported sub-parsers.
    """
    DOCKER_IMAGE = "docker-image"
    DOCKER_CONTAINER = "docker-container"
    FOLDER_SCAN = "folder"
    CLOUD_SCAN = "cloud"
    REPO_SCAN = "repository"
    OPEN_API_SCAN = "open-api"
    CI_CD_GEN = "pipeline"
    ACCOUNT = "account"
    SCAN = "scan"

def auth_token_retrieval(
        coguard_api_url: Optional[str],
        coguard_auth_url: Optional[str]
) -> Optional[Token]:
    """
    The helper function to get the authentication token.
    This may make the user sign up. If the process succeeds,
    it returns the token as string. If the process fails,
    None is being returned.
    """
    auth_config = coguard_cli.auth.util.retrieve_configuration_object(
        arg_coguard_url = coguard_api_url,
        arg_auth_url = coguard_auth_url
    )
    if auth_config is None:
        print(f'{COLOR_YELLOW}Could not find authentication file. You can sign up right now '
              f'for your default account and continue with the requested scan.{COLOR_TERMINATION}')
        coguard_cli.api_connection.log("REGISTRATION_PROMPT", coguard_api_url)
        token = coguard_cli.auth.util.sign_in_or_sign_up(coguard_api_url, coguard_auth_url)
        # Here is where we insert the authentication logic.
        auth_config = coguard_cli.auth.util.retrieve_configuration_object()
    else:
        logging.debug("Retrieving config with auth_config %s", str(auth_config))
        token = Token("", auth_config)
        res = token.authenticate_to_server()
        if res is None:
            token = None
    return token

def validate_output_format(inp_string: str) -> bool:
    """
    A helper function to validate the input for the output format of the CLI.
    """
    choices = ['formatted', 'json', 'sarif', 'markdown']
    if "," not in inp_string and inp_string not in choices:
        raise argparse.ArgumentTypeError(
            f"Invalid output-format choice. Please choose from {choices}."
        )
    inp_strings = inp_string.split(',')
    for elem in inp_strings:
        if elem not in choices:
            raise argparse.ArgumentTypeError(
                f"Invalid output-format choice. Please choose from {choices}."
            )
    return inp_string

def perform_ci_cd_action(
        ci_cd_provider,
        ci_cd_command,
        repository_folder):
    """
    The function to perform a ci_cd_action.
    """
    if repository_folder is not None:
        if not Path(repository_folder).exists():
            print(f"{COLOR_RED}The path you specified did not exist.{COLOR_TERMINATION}")
            sys.exit(1)
    ci_cd_provider_instance = None
    for ci_cd_provider_cls in ci_cd_provider_factory():
        if ci_cd_provider_cls.get_identifier() == ci_cd_provider:
            ci_cd_provider_instance = ci_cd_provider_cls
            break
    if ci_cd_provider_instance is None:
        print(f"{COLOR_RED}Invalid Ci/CD provider given.{COLOR_TERMINATION}")
        sys.exit(1)
    if ci_cd_command == 'add':
        ret_val = ci_cd_provider_instance.add(repository_folder)
        if ret_val is None:
            sys.exit(1)
    else:
        print(f"Invalid command: {ci_cd_command}.")
        sys.exit(1)
    print(ci_cd_provider_instance.post_string())

def docker_image_scan_handler(
        args,
        auth_config,
        deal_type,
        token,
        organization,
        ruleset
):
    """
    The helper function for `entrypoint` for the docker image scan.
    """
    if args.image_name:
        docker_image = args.image_name
    elif args.scan:
        # A small hack to keep scan an optional argument.
        docker_image = args.scan
    else:
        docker_image = None
    image_check.perform_docker_image_scan(
        docker_image,
        auth_config,
        deal_type,
        token,
        organization,
        args.coguard_api_url,
        args.output_format,
        args.fail_level,
        ruleset,
        args.dry_run
    )

def docker_container_scan_handler(
        args,
        auth_config,
        deal_type,
        token,
        organization,
        ruleset
):
    """
    The helper function for `entrypoint` for the docker image scan.
    """
    if args.container_name:
        docker_container = args.container_name
    elif args.scan:
        # A small hack to keep scan an optional argument.
        docker_container = args.scan
    else:
        docker_container = None
    image_check.perform_docker_container_scan(
        docker_container,
        auth_config,
        deal_type,
        token,
        organization,
        args.coguard_api_url,
        args.output_format,
        args.fail_level,
        ruleset,
        args.dry_run
    )

def handle_account_action(args, token, username, organization):
    """
    The helper function for `entrypoint` to handle account actions.
    """
    if args.account_action == 'download-cluster-report':
        if not args.cluster_name:
            print(f"{COLOR_RED}No cluster name provided.{COLOR_TERMINATION}")
            return
        latest_report = coguard_cli.api_connection.get_latest_report(
            token,
            args.coguard_api_url,
            args.cluster_name,
            organization,
            username
        )
        if not latest_report:
            print(
                f"{COLOR_RED}Could not retrieve latest report for "
                f"cluster {args.cluster_name}.{COLOR_TERMINATION}"
            )
            return
        coguard_cli.api_connection.download_report(
            token,
            args.coguard_api_url,
            organization,
            username,
            args.cluster_name,
            latest_report,
            args.download_location
        )
    else:
        print(f"{COLOR_RED}No valid account action provided.{COLOR_TERMINATION}")

def clone_git_repo(url: str) -> str:
    """
    Clones the git repository into a temporary folder and returns the path.
    Returns the empty string if an error occurs.
    """
    dest = tempfile.mkdtemp(prefix = "coguard_repo_extract")
    try:
        subprocess.run(
            ["git", "-C", dest, "clone", url],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )
        subdirs = [os.path.join(dest, name) for name in os.listdir(dest)
                   if os.path.isdir(os.path.join(dest, name))]
        if len(subdirs) != 1:
            return ""
        return subdirs[0]
    except subprocess.CalledProcessError:
        return ""

def download_single_config_file(url: str, filename: str) -> str:
    """
    Downloads a single config file into a temporary folder with a given filename and
    returns the path.
    Returns the empty string if an error occurs.
    """
    tmpdir = tempfile.mkdtemp(prefix = "coguard_single_config_file")
    subpath = replace_special_chars_with_underscore(url)
    dest = pathlib.Path(tmpdir).joinpath(subpath)
    dest.mkdir(exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest.joinpath(filename))
        return str(dest)
    #pylint: disable=broad-exception-caught
    except Exception:
        logging.error("Failed to retrieve the provided URL.")
        return ""

#pylint: disable=too-many-branches
#pylint: disable=too-many-statements
def entrypoint(args):
    """
    The main entrypoint for the CLI. Takes the :mod:`argparse` parsing
    object as parameter.

    :param args: The parsed command line parameters.
    """
    print("""
          XXXXXXXXXXXK
      xXXXXXXXXXXXXXXXXXXl
    XXXXX.            ;XXXXO       .XXXXXXXXXX     oXXXX        XXXXc       xXXXX'       'XXXXXXXXXXXXO     XXXXXXXXXXX;
  lXXXx    lXXXXXXXX,    0XXX;   cXXXXXXXXXXXXXX.  oXXXX        XXXXc      :XXXXXX       'XXXXXXXXXXXXXXX.  XXXXXXXXXXXXXX'
 dXXX.  .XXXXXx  0XXXXX    ...  dXXXX'      cXXXX. oXXXX        XXXXc     .XXXXXXX0      'XXXX'      OXXXX  XXXXo     .XXXXk
;XXX   xXXX    do   .XXXc      'XXXX,              oXXXX        XXXXc     XXXX.oXXXd     'XXXX'      ,XXXX. XXXXd       XXXXd
0XXl  ;XXk     ,,     KXX.     lXXXX               oXXXX        XXXXc    OXXXl  0XXX:    'XXXX'     .XXXXk  XXXXd       lXXXX
XXX:  oXX: cll.  ,ll: oXX;     oXXXX    .XXXXXXXXo oXXXX        XXXXc   oXXXO   .XXXX.   'XXXXXXXXXXXXXX;   XXXXd       lXXXX
OXXo  ;XXO     do     KXX.     cXXXX.   .XXXXXXXXo oXXXX        XXXXc  ;XXXX     :XXXX   'XXXXXXXXXXXXl     XXXXd       xXXX0
;XXX.  oXXX    ,,   .XXX:      .XXXXo        XXXXo lXXXX       .XXXX: .XXXXXXXXXXXXXXXO  'XXXX'   .XXXXd    XXXXd      ,XXXX;
 oXXX.   XXXXXX:lXXXXXK   ;XXX: .XXXXX.      XXXXo  XXXXX     .XXXX0  XXXXx        XXXXo 'XXXX'    .XXXX0   XXXXd    .XXXXX,
  cXXXO    ;XXXXXXXX.    XXXX'    xXXXXXXXXXXXXXX.   kXXXXXXXXXXXXd  kXXXX         ,XXXX:'XXXX'      XXXXK  XXXXXXXXXXXXXl
    KXXXX;            lXXXXx         'XXXXXXX           cXXXXXX;    lXXXX,          dXXXXlXXXX'       KXXXX XXXXXXXXK
      oXXXXXXXXXXXXXXXXXX:
          OXXXXXXXXXXd
    """)
    if not args.dry_run:
        token = auth_token_retrieval(args.coguard_api_url, args.coguard_auth_url)
        if token is None:
            print(f"{COLOR_RED}Failed to authenticate.{COLOR_TERMINATION}")
            return
        auth_config = coguard_cli.auth.util.retrieve_configuration_object(
            arg_coguard_url = args.coguard_api_url,
            arg_auth_url = args.coguard_auth_url
        )
        deal_type = token.extract_deal_type_from_token()
        organization = token.extract_organization_from_token()
    else:
        token=None
        auth_config = CoGuardCliConfig("dry-run-user", None, None, None)
        deal_type = DealEnum.ENTERPRISE
        organization = None
    ruleset = args.ruleset
    logging.debug("Extracted deal type: %s", deal_type)
    logging.debug("Extracted organization: %s", organization)
    if ruleset and deal_type != DealEnum.ENTERPRISE:
        print(f"{COLOR_RED} Ruleset specification is not available in default "
              f"subscriptions {COLOR_TERMINATION}")
        return
    if args.subparsers_location == SubParserNames.DOCKER_IMAGE.value:
        docker_image_scan_handler(
            args,
            auth_config,
            deal_type,
            token,
            organization,
            ruleset
        )
    elif args.subparsers_location == SubParserNames.DOCKER_CONTAINER.value:
        docker_container_scan_handler(
            args,
            auth_config,
            deal_type,
            token,
            organization,
            ruleset
        )
    elif args.subparsers_location == SubParserNames.FOLDER_SCAN.value:
        folder_scan.folder_scan_handler(
            args,
            auth_config,
            deal_type,
            token,
            organization,
            ruleset
        )
    elif args.subparsers_location == SubParserNames.CLOUD_SCAN.value:
        cloud_provider_name = args.cloud_provider_name or args.scan or None
        # args.scan is a trick to
        # think there is a positional argument
        cloud_scan.perform_cloud_provider_scan(
            cloud_provider_name,
            args.credentials_file,
            deal_type,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level,
            ruleset,
            args.dry_run
        )
    elif args.subparsers_location == SubParserNames.REPO_SCAN.value:
        repository_url = args.repo_url or args.scan or None
        if not repository_url:
            print(f"{COLOR_RED} Repository URL needs to be provided.{COLOR_TERMINATION}")
            return
        git_repo_dir = clone_git_repo(repository_url)
        if not git_repo_dir:
            print(f"{COLOR_RED} Could not download requested repository URL.{COLOR_TERMINATION}")
            return
        folder_scan.perform_folder_scan(
            git_repo_dir,
            deal_type,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level,
            ruleset,
            args.dry_run
        )
        shutil.rmtree(git_repo_dir)
    elif args.subparsers_location == SubParserNames.OPEN_API_SCAN.value:
        endpoint_url = args.open_api_url or args.scan or None
        if not endpoint_url:
            print(f"{COLOR_RED} Open API spec URL needs to be provided.{COLOR_TERMINATION}")
            return
        open_api_file_dir = download_single_config_file(
            endpoint_url,
            "openapi.json" if endpoint_url.endswith("json") else "openapi.yml"
        )
        if not open_api_file_dir:
            print(f"{COLOR_RED} Could not download requested openapi spec.{COLOR_TERMINATION}")
            return
        folder_scan.perform_folder_scan(
            open_api_file_dir,
            deal_type,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level,
            ruleset,
            args.dry_run,
            collect_additional_failed_rules = False
        )
        shutil.rmtree(open_api_file_dir)
    elif args.subparsers_location == SubParserNames.CI_CD_GEN.value:
        ci_cd_provider = args.ci_cd_provider_name
        ci_cd_command = args.ci_cd_command
        if ci_cd_command is None:
            print("No command specified")
            sys.exit(1)
        repository_folder = os.path.abspath(args.repository_folder)
        perform_ci_cd_action(
            ci_cd_provider,
            ci_cd_command,
            repository_folder
        )
    elif args.subparsers_location == SubParserNames.ACCOUNT.value:
        handle_account_action(
            args,
            token,
            auth_config.get_username(),
            organization
        )
    elif args.subparsers_location == SubParserNames.SCAN.value:
        image_check.perform_docker_image_scan(
            None,
            auth_config,
            deal_type,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level,
            ruleset,
            args.dry_run
        )
        folder_scan.perform_folder_scan(
            None,
            deal_type,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level,
            ruleset,
            args.dry_run
        )
        for cloud_provider in ["aws", "azure", "gcp"]:
            cloud_scan.perform_cloud_provider_scan(
                cloud_provider,
                args.credentials_file,
                deal_type,
                auth_config,
                token,
                organization,
                args.coguard_api_url,
                args.output_format,
                args.fail_level,
                ruleset,
                args.dry_run
            )

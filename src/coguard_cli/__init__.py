"""
The CoGuard CLI top level entrypoint where the entrypoint function is being defined
"""

from enum import Enum
import json
import shutil
import os
import sys
import textwrap
import logging
from typing import Dict, Optional, Tuple

from coguard_cli.image_check import create_zip_to_upload_from_docker_image, docker_dao
from coguard_cli.folder_scan import create_zip_to_upload_from_file_system
from coguard_cli.discovery.cloud_discovery.cloud_provider_factory import cloud_provider_factory
from coguard_cli import auth
from coguard_cli import api_connection
from coguard_cli.print_colors import COLOR_TERMINATION, \
    COLOR_RED, COLOR_GRAY, COLOR_CYAN, COLOR_YELLOW

def print_failed_check(color: str, entry: Dict, manifest_dict: Dict):
    """
    This is the function to print a failed check entry, given a color.

    :param color: The color to use. see e.g. :const:`COLOR_RED`
    :param entry: The entry as returned by the CoGuard API.
    :param manifest_dict: The manifest dictionary containing information about the included
                          configuration files
    """
    machines_dict = manifest_dict.get("machines", {})
    reference = ""
    for machine in machines_dict.values():
        services_dict = machine.get("services", {})
        if entry.get("service") in services_dict:
            config_file_list_of_container = \
                [
                    os.path.join(entry["subPath"], entry["fileName"])
                    for entry in services_dict.get(entry.get("service")).get("configFileList", [])
                ]
            if config_file_list_of_container:
                reference = f" (affected files: {', '.join(config_file_list_of_container)})"
                break
    if not reference:
        # Could be in cluster services
        services_dict = manifest_dict.get("clusterServices", {})
        if entry.get("service") in services_dict:
            config_file_list_of_container = \
                [
                    os.path.join(entry["subPath"], entry["fileName"])
                    for entry in services_dict.get(entry.get("service")).get("configFileList", [])
                ]
            if config_file_list_of_container:
                reference = f" (affected files: {', '.join(config_file_list_of_container)})"
    print(
        f'{color} X Severity {entry["rule"]["severity"]}: '
        f'{entry["rule"]["name"]}{COLOR_TERMINATION}'
        f'{reference}'
    )
    prefix = "Documentation: "
    try:
        terminal_size = os.get_terminal_size().columns
    except OSError:
        terminal_size = 80
    wrapper = textwrap.TextWrapper(
        initial_indent=prefix,
        width=max(80, terminal_size//2),
        subsequent_indent=' '*len(prefix)
    )
    print(wrapper.fill(entry["rule"]["documentation"]))

def output_result_json_from_coguard(result_json: Dict, manifest_dict: Dict):
    """
    The function which outputs the result json in a pretty format to the screen.

    :param result_json: The output from the API call to CoGuard.
    :param manifest_dict: The manifest dictionary containing information about the included
                          configuration files
    """
    high_checks = [entry for entry in result_json.get("failed", []) \
                   if entry["rule"]["severity"] > 3]
    high_checks.sort(key = lambda x: x["rule"]["severity"], reverse=True)
    medium_checks = [entry for entry in result_json.get("failed", []) \
                     if entry["rule"]["severity"] == 3]
    medium_checks.sort(key = lambda x: x["rule"]["severity"], reverse=True)
    low_checks = [entry for entry in result_json.get("failed", []) if entry["rule"]["severity"] < 3]
    low_checks.sort(key = lambda x: x["rule"]["severity"], reverse=True)
    print(f'Scan result_jsons: {len(result_json.get("failed", []))} checks failed, '
          f"{COLOR_RED}{len(high_checks)} High{COLOR_TERMINATION}/"
          f"{COLOR_YELLOW}{len(medium_checks)} Medium{COLOR_TERMINATION}/"
          f"{COLOR_GRAY}{len(low_checks)} Low{COLOR_TERMINATION}")
    for entry in high_checks:
        print_failed_check(COLOR_RED, entry, manifest_dict)
    for entry in medium_checks:
        print_failed_check(COLOR_YELLOW, entry, manifest_dict)
    for entry in low_checks:
        print_failed_check(COLOR_GRAY, entry, manifest_dict)

class SubParserNames(Enum):
    """
    The enumeration capturing the different supported sub-parsers.
    """
    DOCKER_IMAGE = "docker-image"
    FOLDER_SCAN = "folder"
    CLOUD_SCAN = "cloud"
    SCAN = "scan"

def auth_token_retrieval(
        coguard_api_url: Optional[str],
        coguard_auth_url: Optional[str]
) -> Optional[auth.token.Token]:
    """
    The helper function to get the authentication token.
    This may make the user sign up. If the process succeeds,
    it returns the token as string. If the process fails,
    None is being returned.
    """
    auth_config = auth.retrieve_configuration_object(
        arg_coguard_url = coguard_api_url,
        arg_auth_url = coguard_auth_url
    )
    if auth_config is None:
        print(f'{COLOR_YELLOW}Could not find authentication file. You can sign up right now '
              f'for your free account and continue with the requested scan.{COLOR_TERMINATION}')
        token = auth.sign_in_or_sign_up(coguard_api_url, coguard_auth_url)
        # Here is where we insert the authentication logic.
        auth_config = auth.retrieve_configuration_object()
    else:
        logging.debug("Retrieving config with auth_config %s", str(auth_config))
        token = auth.token.Token("", auth_config)
        res = token.authenticate_to_server()
        if res is None:
            token = None
    return token

def upload_and_evaluate_zip_candidate(
        zip_candidate: Optional[Tuple[str, Dict]],
        auth_config: Optional[auth.auth_config.CoGuardCliConfig],
        token: auth.token.Token,
        coguard_api_url: str,
        scan_identifier: str,
        output_format: str,
        fail_level: int,
        organization: Optional[str]
):
    """
    The common function to upload a zip file, as generated by the
    helper functions, and evaluate the returned result.
    """
    if zip_candidate is None:
        print(
            f"{COLOR_YELLOW}Unable to identify any known configuration files.{COLOR_TERMINATION}"
        )
        return
    zip_file, manifest_dict = zip_candidate
    result = api_connection.send_zip_file_for_scanning(
        zip_file,
        auth_config.get_username(),
        token,
        coguard_api_url,
        scan_identifier,
        organization
    )
    logging.debug("The result from the api is: %s",
                  str(result))
    print(f"{COLOR_CYAN}SCANNING OF{COLOR_TERMINATION} {scan_identifier}"
          f" {COLOR_CYAN}COMPLETED{COLOR_TERMINATION}")
    if output_format == 'formatted':
        output_result_json_from_coguard(result or {}, manifest_dict)
    else:
        print(json.dumps(result or {}))
    #os.remove(zip_file)
    max_fail_severity = max(
        entry["rule"]["severity"] for entry in result.get("failed", [])
    ) if (result and result.get("failed", [])) else 0
    if max_fail_severity >= fail_level:
        sys.exit(1)

def perform_docker_image_scan(
        docker_image: Optional[str],
        auth_config: auth.CoGuardCliConfig,
        token: auth.token.Token,
        organization: str,
        coguard_api_url: Optional[str],
        output_format: str,
        fail_level: int):
    """
    The helper function to run a Docker image scan. It takes in all necessary parameters.
    If the docker-image is None, then all Docker images found on the host system are being
    scanned.
    """
    docker_version = docker_dao.check_docker_version()
    if docker_version is None:
        print(f'{COLOR_RED}Docker is not installed on your system. '
              f'Please install Docker to proceed{COLOR_TERMINATION}')
        return
    print(f'{docker_version} detected.')
    if docker_image:
        images = [docker_image]
    else:
        print(
            f"{COLOR_CYAN}No image name provided, scanning all images "
            f"installed on this machine.{COLOR_TERMINATION}"
        )
        images = docker_dao.extract_all_installed_docker_images()
    for image in images:
        print(f"{COLOR_CYAN}SCANNING IMAGE {COLOR_TERMINATION}{image}")
        zip_candidate = create_zip_to_upload_from_docker_image(
            auth_config.get_username(),
            image,
            auth.util.DealEnum.ENTERPRISE
        )
        if zip_candidate is None:
            print(f"{COLOR_YELLOW}Image {image} - NO CONFIGURATION FILES FOUND.")
        upload_and_evaluate_zip_candidate(
            zip_candidate,
            auth_config,
            token,
            coguard_api_url,
            docker_image,
            output_format,
            fail_level,
            organization
        )

def perform_folder_scan(
        folder_name: Optional[str],
        deal_type: auth.util.DealEnum,
        auth_config: auth.CoGuardCliConfig,
        token: auth.token.Token,
        organization: str,
        coguard_api_url: Optional[str],
        output_format: str,
        fail_level: int):
    """
    Helper function to run a scan on a folder. If the folder_name parameter is None,
    the current working directory is being used.
    """
    if deal_type != auth.util.DealEnum.ENTERPRISE:
        print("Folder scanning is only available for non-free accounts")
        sys.exit(1)
    folder_name = folder_name or "."
    printed_folder_name = os.path.basename(os.path.dirname(folder_name + os.sep))
    print(f"{COLOR_CYAN}SCANNING FOLDER {COLOR_TERMINATION}{printed_folder_name}")
    zip_candidate = create_zip_to_upload_from_file_system(
        folder_name,
        organization
    )
    if zip_candidate is None:
        print(f"{COLOR_YELLOW}FOLDER {printed_folder_name} - NO CONFIGURATION FILES FOUND.")
    upload_and_evaluate_zip_candidate(
        zip_candidate,
        auth_config,
        token,
        coguard_api_url,
        printed_folder_name,
        output_format,
        fail_level,
        organization
    )

def perform_cloud_provider_scan(
        cloud_provider_name: Optional[str],
        deal_type: auth.util.DealEnum,
        auth_config: auth.CoGuardCliConfig,
        token: auth.token.Token,
        organization: str,
        coguard_api_url: Optional[str],
        output_format: str,
        fail_level: int):
    """
    Helper function to run a scan on a folder. If the folder_name parameter is None,
    the current working directory is being used.
    """
    if deal_type != auth.util.DealEnum.ENTERPRISE:
        print("Cloud provider scanning is only available for non-free accounts")
        sys.exit(1)
    provider_name = cloud_provider_name or "aws"
    print(f"{COLOR_CYAN}SCANNING CLOUD_PROVIDER {COLOR_TERMINATION}{provider_name}")
    cloud_provider = None
    for cloud_provider in cloud_provider_factory():
        logging.debug("Checking if %s matches.", cloud_provider.get_cloud_provider_name())
        if cloud_provider.get_cloud_provider_name() == cloud_provider_name:
            break
    if not cloud_provider or cloud_provider.get_cloud_provider_name() != cloud_provider_name:
        logging.error("The cloud provider you requested is not implemented yet.")
        sys.exit(1)
    folder_name = cloud_provider.extract_iac_files_for_account(
        auth_config,
    )
    if not folder_name:
        logging.error("Unable to extract the requested cloud provider %s.",
                      cloud_provider_name)
        sys.exit(1)
    zip_candidate = create_zip_to_upload_from_file_system(
        folder_name,
        organization,
        f"{provider_name}_extraction"
    )
    shutil.rmtree(folder_name)
    if zip_candidate is None:
        print(f"{COLOR_YELLOW}Cloud Provider {cloud_provider_name} - NO CONFIGURATION FILES FOUND.")
    upload_and_evaluate_zip_candidate(
        zip_candidate,
        auth_config,
        token,
        coguard_api_url,
        f"{provider_name}_extraction",
        output_format,
        fail_level,
        organization
    )

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
    token = auth_token_retrieval(args.coguard_api_url, args.coguard_auth_url)
    if token is None:
        print(f"{COLOR_RED}Failed to authenticate.{COLOR_TERMINATION}")
        return
    auth_config = auth.retrieve_configuration_object(
        arg_coguard_url = args.coguard_api_url,
        arg_auth_url = args.coguard_auth_url
    )
    deal_type = token.extract_deal_type_from_token()
    organization = token.extract_organization_from_token()
    logging.debug("Extracted deal type: %s", deal_type)
    logging.debug("Extracted organization: %s", organization)
    if args.subparsers_location == SubParserNames.DOCKER_IMAGE.value:
        if args.image_name:
            docker_image = args.image_name
        elif args.scan:
            # A small hack to keep scan an optional argument.
            docker_image = args.scan
        else:
            docker_image = None
        perform_docker_image_scan(
            docker_image,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level
        )
    elif args.subparsers_location == SubParserNames.FOLDER_SCAN.value:
        folder_name = args.folder_name or args.scan or None # args.scan is a trick to
                                                            # think there is a positional argument
        perform_folder_scan(
            folder_name,
            deal_type,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level
        )
    elif args.subparsers_location == SubParserNames.CLOUD_SCAN.value:
        cloud_provider_name = args.cloud_provider_name or args.scan or None
        # args.scan is a trick to
        # think there is a positional argument
        perform_cloud_provider_scan(
            cloud_provider_name,
            deal_type,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level
        )
    elif args.subparsers_location == SubParserNames.SCAN.value:
        perform_docker_image_scan(
            None,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level
        )
        perform_folder_scan(
            None,
            deal_type,
            auth_config,
            token,
            organization,
            args.coguard_api_url,
            args.output_format,
            args.fail_level
        )

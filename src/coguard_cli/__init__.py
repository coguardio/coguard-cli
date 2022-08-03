"""
The CoGuard CLI top level entrypoint where the entrypoint function is being defined
"""

import json
import os
import sys
import textwrap
from typing import Dict

from coguard_cli.image_check import create_zip_to_upload_from_docker_image, docker_dao
from coguard_cli.auth import DealEnum, \
    authenticate_to_server, \
    retrieve_configuration_object, \
    sign_in_or_sign_up
from coguard_cli.api_connection import send_zip_file_for_scanning
from coguard_cli.print_colors import COLOR_TERMINATION, \
    COLOR_RED, COLOR_GRAY, COLOR_CYAN, COLOR_YELLOW

def print_failed_check(color: str, entry: Dict):
    """
    This is the function to print a failed check entry, given a color.

    :param color: The color to use. see e.g. :const:`COLOR_RED`
    :param entry: The entry as returned by the CoGuard API.
    """
    print(
        f'{color} X Severity {entry["rule"]["severity"]}: '
        f'{entry["rule"]["name"]}{COLOR_TERMINATION}'
    )
    prefix = "Documentation: "
    try:
        terminal_size = os.get_terminal_size().columns
    except OSError:
        terminal_size = 80
    wrapper = textwrap.TextWrapper(
        initial_indent=prefix,
        width=max(80, terminal_size/2),
        subsequent_indent=' '*len(prefix)
    )
    print(wrapper.fill(entry["rule"]["documentation"]))

def output_result_json_from_coguard(result_json: Dict):
    """
    The function which outputs the result json in a pretty format to the screen.

    :param result_json: The output from the API call to CoGuard.
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
        print_failed_check(COLOR_RED, entry)
    for entry in medium_checks:
        print_failed_check(COLOR_YELLOW, entry)
    for entry in low_checks:
        print_failed_check(COLOR_GRAY, entry)

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
    docker_version = docker_dao.check_docker_version()
    if docker_version is None:
        print(f'{COLOR_RED}Docker is not installed on your system. '
              f'Please install Docker to proceed{COLOR_TERMINATION}')
        return
    print(f'{docker_version} detected.')
    auth_config = retrieve_configuration_object()
    if auth_config is None:
        print(f'{COLOR_YELLOW}Could not find authentication file. You can sign up right now '
              f'for your free account and continue with the requested scan.{COLOR_TERMINATION}')
        token = sign_in_or_sign_up(args.coguard_api_url, args.coguard_auth_url)
        # Here is where we insert the authentication logic.
        auth_config = retrieve_configuration_object()
    else:
        token = authenticate_to_server(auth_config)
    if token is None:
        print(f"{COLOR_RED}Failed to authenticate.{COLOR_TERMINATION}")
        return
    if args.image_name:
        images = [args.image_name]
    else:
        print(
            f"{COLOR_CYAN}No image name provided, scanning all images "
            f"installed on this machine.{COLOR_TERMINATION}"
        )
        images = docker_dao.extract_all_installed_docker_images()
    for image in images:
        print(f"{COLOR_CYAN}SCANNING IMAGE {COLOR_TERMINATION}{image}")
        zip_file = create_zip_to_upload_from_docker_image(
            auth_config.get_username(),
            image,
            DealEnum.ENTERPRISE
        )
        if zip_file is None:
            print(
                f"{COLOR_YELLOW}We were unable to extract any known "
                "configuration files from the given "
                "image name. If you believe that this is due to a bug, please report it "
                f"to info@coguard.io{COLOR_TERMINATION}"
            )
            return
        result = send_zip_file_for_scanning(
            zip_file,
            auth_config.get_username(),
            token,
            args.coguard_api_url
        )
        os.remove(zip_file)
        print(f"{COLOR_CYAN}SCANNING OF{COLOR_TERMINATION} {image}"
              f" {COLOR_CYAN}COMPLETED{COLOR_TERMINATION}")
        if args.output_format == 'formatted':
            output_result_json_from_coguard(result)
        else:
            print(json.dumps(result))
        min_fail_level = min(
            entry["rule"]["severity"] for entry in result.get("failed", [])
        )
        if min_fail_level >= args.fail_level:
            sys.exit(1)

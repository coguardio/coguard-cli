"""
The main function is hosted here, and it will be the entrypoint for the command line
interface
"""

import argparse
import logging
from coguard_cli import entrypoint

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
        default='https://portal.coguard.io/server',
        help='The url of the coguard api to call',
    )
    parser.add_argument(
        '--coguard-auth-url',
        type=str,
        dest='coguard_auth_url',
        default='https://portal.coguard.io',
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
    subparsers = parser.add_subparsers(
        required=True
    )
    docker_image_parser = subparsers.add_parser(
        'docker-image',
        help="The sub-command, which is currently limited to `docker-image`"
    )
    docker_image_parser.add_argument(
        'image_name',
        metavar="image_name",
        type=str,
        default="",
        nargs='?',
        help=("The name of the image. Defaults to empty string, "
              "which means all images are being scanned.")
    )
    args = parser.parse_args()
    set_logging_config(args.logging_level)
    entrypoint(args)

if __name__ == '__main__':
    main()

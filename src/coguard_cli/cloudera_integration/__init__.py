"""
The operational side of the CoGuard Cloudera integration.

`coguard cloud cloudera` scans a Cloudera cluster once, when a person asks it
to. The two entry points in this package are what turn that into a standing
report:

* `coguard-cloudera-check` asks Cloudera Manager whether the configuration of
  the cluster has moved, and runs that scan when it has.
* `coguard-cloudera-banner` takes the result of a scan and shows a summary of it
  in the header of Cloudera Manager, so that the state of the configuration is
  visible where the cluster is administered.

Everything in here talks to Cloudera Manager through `GET` requests only, with
the single exception of the one `PUT` which writes the banner. That request lives
in `banner.py`, in a client of its own, so that the client used for scanning
stays a reader. None of it takes a password on the command line.
"""

import argparse
import logging
from typing import Dict, Optional

from coguard_cli.discovery.cloud_discovery.cloud_providers.cloud_provider_cloudera \
    import CloudProviderCloudera
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi, ClouderaManagerApiError
from coguard_cli.print_colors import COLOR_RED, COLOR_TERMINATION

# The exit codes this entry point produces itself. A check which ran a scan
# exits with the exit code of that scan instead, so that what a pipeline sees is
# what `coguard` decided.
EXIT_CLEAN = 0
EXIT_ERROR = 2


def add_cloudera_manager_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Adds the Cloudera Manager connection arguments to a parser.

    The names are the ones `coguard cloud cloudera` uses, so that moving from a
    manual scan to a scheduled one does not mean learning a second set of
    options. As there, the password is deliberately not among them: it is taken
    from the CLOUDERA_MANAGER_PASSWORD environment variable, from a credentials
    file, or asked for interactively, so that it stays out of the shell history
    and out of the process list.
    """
    parser.add_argument(
        '--cloudera-manager-url',
        type=str,
        dest='cloudera_manager_url',
        required=False,
        help=("The URL of the Cloudera Manager instance, e.g. "
              "`https://cm.example.com`. Can also be provided via the "
              "CLOUDERA_MANAGER_URL environment variable.")
    )
    parser.add_argument(
        '--cloudera-manager-user',
        type=str,
        dest='cloudera_manager_user',
        required=False,
        help=("The Cloudera Manager user to authenticate as. Can also be "
              "provided via the CLOUDERA_MANAGER_USER environment variable.")
    )
    parser.add_argument(
        '--cloudera-manager-ca-cert',
        type=str,
        dest='cloudera_manager_ca_cert',
        required=False,
        help=("The path to a CA certificate bundle to trust when connecting to "
              "Cloudera Manager. Can also be provided via the "
              "CLOUDERA_MANAGER_CA_CERT environment variable.")
    )
    parser.add_argument(
        '--cloudera-manager-no-verify-tls',
        action='store_true',
        dest='cloudera_manager_no_verify_tls',
        default=False,
        required=False,
        help=("Do not verify the TLS certificate of Cloudera Manager. Useful "
              "for deployments behind a reverse proxy with a self-signed "
              "certificate.")
    )
    parser.add_argument(
        '--cloudera-cluster',
        type=str,
        dest='cloudera_cluster',
        required=False,
        help=("The name of the cluster to scan. Only required if the Cloudera "
              "Manager instance manages more than one cluster.")
    )
    parser.add_argument(
        '--credentials-file',
        type=str,
        dest='credentials_file',
        required=False,
        help=("A JSON or YAML file with the keys `url`, `username`, "
              "`password`, `ca_cert`, `verify_tls` and `cluster`.")
    )
    parser.add_argument(
        '--logging-level',
        type=str,
        dest='logging_level',
        required=False,
        default="INFO",
        help=("The logging level of this call. Can be one of the following: "
              "DEBUG, INFO, WARNING, ERROR, CRITICAL.")
    )


def apply_logging_level(args: argparse.Namespace) -> None:
    """
    Applies the requested logging level, defaulting to INFO if it is not one
    the logging module knows.
    """
    logging.basicConfig(
        format='%(asctime)s %(levelname)s: %(message)s',
        level=getattr(logging,
                      str(getattr(args, "logging_level", "INFO")).upper(),
                      logging.INFO)
    )


def cloudera_manager_options(args: argparse.Namespace) -> Dict:
    """
    Collects the Cloudera Manager connection parameters which were actually
    provided on the command line, in the shape the Cloudera cloud provider
    expects them.
    """
    option_by_argument = {
        "cloudera_manager_url": "url",
        "cloudera_manager_user": "username",
        "cloudera_manager_ca_cert": "ca_cert",
        "cloudera_cluster": "cluster",
    }
    result = {}
    for argument_name, option_name in option_by_argument.items():
        value = getattr(args, argument_name, None)
        if value:
            result[option_name] = value
    if getattr(args, "cloudera_manager_no_verify_tls", False):
        result["verify_tls"] = False
    return result


def resolve_credentials(args: argparse.Namespace) -> Optional[Dict]:
    """
    Resolves the Cloudera Manager credentials with the precedence the Cloudera
    provider of the CLI establishes: command line, credentials file,
    environment. `None` is returned if the connection cannot be described.
    """
    provider = CloudProviderCloudera(cloudera_manager_options(args))
    return provider.extract_credentials(
        getattr(args, "credentials_file", None)
    )


def connect(credentials: Dict) -> Optional[ClouderaManagerApi]:
    """
    Creates a Cloudera Manager API client from resolved credentials and
    verifies that it can reach Cloudera Manager. `None` is returned, with the
    reason printed, if it cannot.
    """
    try:
        api = ClouderaManagerApi(
            base_url=credentials["url"],
            username=credentials["username"],
            password=credentials["password"],
            verify_tls=credentials.get("verify_tls", True),
            ca_cert=credentials.get("ca_cert")
        )
    except ClouderaManagerApiError as err:
        print(f"{COLOR_RED}{err}{COLOR_TERMINATION}")
        return None
    if not api.check_connection():
        print(f"{COLOR_RED}Could not connect to Cloudera Manager at "
              f"{credentials['url']}.{COLOR_TERMINATION}")
        return None
    return api

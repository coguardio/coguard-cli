"""
The `coguard-cloudera-banner` entry point.

It takes the result of a scan and puts a summary of it into the header of
Cloudera Manager, so that the state of the configuration is visible to the people
who administer the cluster in the place where they administer it, rather than
only in a portal they have to remember to open.

The parameter written is `CUSTOM_BANNER_HTML` of the Cloudera Manager service
configuration, which Cloudera provides for exactly this purpose ("The custom
banner is used to display customer specific text in the header area.") and which
is rendered as raw HTML on every page. Three consequences follow from that, and
they are what most of this module is about:

* **Everything taken from the result is escaped.** A rule name, a service name
  and a file name all end up inside the markup, and all three come from data. An
  unescaped `<` in any of them would be markup in the header of every page of
  Cloudera Manager for every user.
* **The banner is shared.** A customer may already display something in it, a
  maintenance notice or the name of the environment, and that text is not ours to
  remove. The part written here is therefore delimited by
  `<!--coguard:start-->` and `<!--coguard:end-->`, the current value is read
  before it is written, and only the region between the delimiters is replaced.
* **It has to stay short.** It is a header, not a report. Only the counts and
  the worst affected services are shown, capped by `--max-services`, and the
  detail stays in the report the banner links to.

This is the one part of the Cloudera integration which changes the cluster. The
client used for scanning issues `GET` requests only, on purpose, so the single
`PUT` lives in `ClouderaManagerBannerApi` in this module, which is used by
nothing else. Writing the Cloudera Manager service configuration requires the
Full Administrator role, unlike the read-only scan, so this command is meant to
be given a credential of its own rather than the one the scan uses.
"""

import argparse
import datetime
import html
import json
import logging
import pathlib
from typing import Dict, List, Optional, Tuple

import requests

from coguard_cli.cloudera_integration import EXIT_CLEAN, EXIT_ERROR, \
    add_cloudera_manager_arguments, apply_logging_level, resolve_credentials
from coguard_cli.discovery.cloudera_discovery import determine_cluster_name
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi, ClouderaManagerApiError
from coguard_cli.print_colors import COLOR_CYAN, COLOR_RED, \
    COLOR_TERMINATION, COLOR_YELLOW

# The Cloudera Manager configuration parameter holding the text of the header
# banner.
BANNER_PARAMETER = "CUSTOM_BANNER_HTML"
# The delimiters of the region of the banner this command owns. Everything
# outside of them belongs to whoever put it there and is preserved verbatim.
BLOCK_START = "<!--coguard:start-->"
BLOCK_END = "<!--coguard:end-->"
# How many services are named in the banner before the rest is summarized as a
# count. The banner is a header, so this is deliberately small.
DEFAULT_MAX_SERVICES = 5
# How a severity is named in the banner. These are the three buckets the CLI
# prints a scan result in, and the banner uses them so that the header of
# Cloudera Manager and the output of the scan say the same thing about the same
# finding.
SEVERITY_BUCKETS = (
    (4, "High"),
    (3, "Medium"),
    (1, "Low"),
)


def severity_bucket(severity: int) -> str:
    """
    Names the bucket a severity falls into, the way the CLI does when it prints
    a scan result.
    """
    for threshold, name in SEVERITY_BUCKETS:
        if severity >= threshold:
            return name
    return "Low"


class ClouderaManagerBannerApi(ClouderaManagerApi):
    """
    The Cloudera Manager client of this command, which is the only one in the
    integration that writes.

    It exists as a class of its own so that the client used for scanning stays
    what it says it is, a reader. The url assembly, the API version negotiation
    and the TLS configuration are inherited, since a write has exactly the same
    need for them as a read.
    """

    def get_cm_config(self) -> Optional[Dict[str, Optional[str]]]:
        """
        Returns the Cloudera Manager service configuration as a mapping of
        parameter name to value, or `None` if it could not be read. A parameter
        which is not set has the value `None`, which is how Cloudera Manager
        reports it and how it differs from a parameter set to the empty string.
        """
        response = self._get("cm", "config", query_parameters={"view": "full"})
        if response is None:
            logging.error("Could not read the Cloudera Manager configuration.")
            return None
        try:
            items = response.json().get("items", []) or []
        except ValueError as err:
            logging.error("Could not decode the Cloudera Manager "
                          "configuration: %s", err)
            return None
        return {
            item["name"]: item.get("value")
            for item in items
            if isinstance(item, dict) and item.get("name")
        }

    def put_cm_config(self, name: str, value: str) -> bool:
        """
        Sets a single parameter of the Cloudera Manager service configuration.

        This is the only request in the whole integration which is not a `GET`.
        A partial update is sent, i.e. the request names the one parameter to
        change, which is how Cloudera Manager expects it and what keeps the other
        281 parameters of the resource out of the picture entirely.
        """
        url = self._api_url("cm", "config")
        logging.debug("Writing %s through %s", name, url)
        try:
            response = self._session.put(
                url,
                json={"items": [{"name": name, "value": value}]},
                timeout=self._timeout
            )
            response.raise_for_status()
        except requests.RequestException as err:
            logging.error("Could not write %s: %s", name, err)
            return False
        return True


def read_result(result_file: str) -> Optional[Dict]:
    """
    Reads the result JSON of a scan, as written by
    `coguard --output-format json`.
    """
    path = pathlib.Path(result_file)
    if not path.is_file():
        print(f"{COLOR_RED}There is no scan result at {result_file}. Run "
              f"`coguard --output-format json cloud cloudera` first."
              f"{COLOR_TERMINATION}")
        return None
    try:
        with path.open('r', encoding='utf-8') as result_stream:
            result = json.load(result_stream)
    except (OSError, ValueError) as err:
        print(f"{COLOR_RED}Could not read the scan result at {result_file}: "
              f"{err}{COLOR_TERMINATION}")
        return None
    if not isinstance(result, dict):
        print(f"{COLOR_RED}The scan result at {result_file} is not a CoGuard "
              f"result.{COLOR_TERMINATION}")
        return None
    return result


def failed_findings(result: Dict, minimum_severity: int) -> List[Dict]:
    """
    Returns the failed checks of a result which are at or above a severity.

    A result of a cluster scan reports a failed check with the cluster service it
    belongs to under `service`, which for this integration is the
    `{service}_{role type}` name the scan assigned, and with the rule under
    `rule`.
    """
    return [
        entry for entry in result.get("failed", []) or []
        if isinstance(entry, dict)
        and isinstance(entry.get("rule"), dict)
        and int(entry["rule"].get("severity", 0)) >= minimum_severity
    ]


def summarize(findings: List[Dict]) -> Tuple[List[Tuple[str, int]],
                                             List[Tuple[str, int]]]:
    """
    Counts the findings by severity bucket and by cluster service.

    The buckets are returned in the order the CLI prints them, worst first, and
    only those which occur. The services are returned worst first as well, i.e.
    ordered by the severity of their worst finding and then by how many they
    have, so that a cap on how many are shown keeps the ones that matter.
    """
    count_by_bucket: Dict[str, int] = {}
    count_by_service: Dict[str, int] = {}
    worst_by_service: Dict[str, int] = {}
    for finding in findings:
        severity = int(finding["rule"].get("severity", 0))
        bucket = severity_bucket(severity)
        count_by_bucket[bucket] = count_by_bucket.get(bucket, 0) + 1
        service = str(finding.get("service") or "the cluster")
        count_by_service[service] = count_by_service.get(service, 0) + 1
        worst_by_service[service] = max(worst_by_service.get(service, 0),
                                        severity)
    buckets = [
        (name, count_by_bucket[name])
        for _, name in SEVERITY_BUCKETS
        if name in count_by_bucket
    ]
    services = sorted(
        count_by_service.items(),
        key=lambda item: (-worst_by_service[item[0]], -item[1], item[0])
    )
    return buckets, services


def render_block(findings: List[Dict],
                 cluster_name: Optional[str],
                 report_url: Optional[str],
                 max_services: int) -> str:
    """
    Renders the region of the banner this command owns.

    Every value which comes from the scan result is escaped, since the banner is
    rendered as raw HTML. The markup is inline styled, because the banner is
    injected into a page whose stylesheet belongs to Cloudera Manager and which
    has no class of ours to hook into.
    """
    scanned_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    where = f" of {html.escape(cluster_name)}" if cluster_name else ""
    if not findings:
        headline = (
            f"CoGuard: the configuration{where} has no findings "
            f"(scanned {scanned_at})."
        )
        color = "#1a7f37"
    else:
        buckets, services = summarize(findings)
        counts = ", ".join(f"{count} {name}" for name, count in buckets)
        shown = services[:max_services]
        named = ", ".join(
            f"{html.escape(service)} ({count})" for service, count in shown
        )
        remaining = len(services) - len(shown)
        if remaining > 0:
            named += f" and {remaining} further service" \
                     f"{'s' if remaining > 1 else ''}"
        headline = (
            f"CoGuard: {len(findings)} configuration finding"
            f"{'s' if len(findings) > 1 else ''}{where} ({counts}), affecting "
            f"{named}. Scanned {scanned_at}."
        )
        color = "#b42318"
    link = ""
    if report_url:
        # The url is a command line argument rather than result data, but it is
        # escaped all the same, since it ends up in an attribute.
        link = (f' <a href="{html.escape(report_url, quote=True)}" '
                f'style="color:inherit;text-decoration:underline;">'
                f'Full report</a>.')
    return (
        f'{BLOCK_START}'
        f'<span style="color:{color};font-weight:bold;">{headline}</span>'
        f'{link}'
        f'{BLOCK_END}'
    )


def replace_block(current_value: Optional[str], block: str) -> str:
    """
    Puts a block into the current banner, replacing an earlier one of ours and
    leaving everything else untouched. An empty block removes the region
    entirely.

    A banner whose start delimiter has no end delimiter after it was written by
    an interrupted run of this command. Everything from that delimiter onwards is
    then ours and is dropped, since what came before it is the part that belongs
    to somebody else.
    """
    current = current_value or ""
    start = current.find(BLOCK_START)
    end = current.find(BLOCK_END, start + len(BLOCK_START)) if start >= 0 else -1
    if start >= 0:
        before = current[:start]
        after = current[end + len(BLOCK_END):] if end > start else ""
    else:
        before = current
        after = ""
    before = before.rstrip()
    if not block:
        return f"{before} {after.strip()}".strip()
    separator = " " if before else ""
    return f"{before}{separator}{block}{after}".rstrip()


def argument_parser() -> argparse.ArgumentParser:
    """
    The command line of `coguard-cloudera-banner`.
    """
    parser = argparse.ArgumentParser(
        prog="coguard-cloudera-banner",
        description=(
            "Show the result of a CoGuard scan in the header of Cloudera "
            "Manager. Only the region between the CoGuard delimiters of the "
            "banner is written, so an existing banner is kept."
        )
    )
    add_cloudera_manager_arguments(parser)
    parser.add_argument(
        '--result-file',
        type=str,
        dest='result_file',
        default="result.json",
        required=False,
        help=("The result JSON of the scan, as written by `coguard "
              "--output-format json`. Defaults to `result.json` in the current "
              "directory.")
    )
    parser.add_argument(
        '--minimum-severity',
        type=int,
        dest='minimum_severity',
        default=1,
        required=False,
        help=("Only count findings at or above this severity. Defaults to 1, "
              "i.e. all of them.")
    )
    parser.add_argument(
        '--max-services',
        type=int,
        dest='max_services',
        default=DEFAULT_MAX_SERVICES,
        required=False,
        help=(f"How many affected services to name before summarizing the rest "
              f"as a count. Defaults to {DEFAULT_MAX_SERVICES}.")
    )
    parser.add_argument(
        '--report-url',
        type=str,
        dest='report_url',
        required=False,
        help=("The address the banner links to for the full report, e.g. the "
              "cluster in the CoGuard portal.")
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        dest='clear',
        default=False,
        required=False,
        help=("Remove the CoGuard region from the banner and write nothing "
              "else. No scan result is read.")
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        dest='dry_run',
        default=False,
        required=False,
        help=("Print the banner which would be written, and do not write it. "
              "Nothing is changed, and the current banner is still read.")
    )
    return parser


def connect_for_writing(credentials: Dict) -> Optional[ClouderaManagerBannerApi]:
    """
    Creates the writing client and verifies that Cloudera Manager accepts the
    credentials. The role the credentials need here is Full Administrator, since
    the Cloudera Manager service configuration is what is written.
    """
    try:
        api = ClouderaManagerBannerApi(
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


def determine_block(args: argparse.Namespace,
                    cluster_name: Optional[str]) -> Optional[str]:
    """
    Produces the block to put into the banner, which is empty when the region is
    to be removed. `None` means the result could not be read, and nothing should
    be written.
    """
    if args.clear:
        return ""
    result = read_result(args.result_file)
    if result is None:
        return None
    findings = failed_findings(result, args.minimum_severity)
    return render_block(
        findings,
        cluster_name,
        args.report_url,
        max(1, args.max_services)
    )


def write_banner(api: ClouderaManagerBannerApi,
                 block: str,
                 dry_run: bool) -> int:
    """
    Puts a block into the banner of Cloudera Manager, leaving whatever else is in
    the banner alone, and returns the exit code of doing so.
    """
    configuration = api.get_cm_config()
    if configuration is None:
        return EXIT_ERROR
    if BANNER_PARAMETER not in configuration:
        print(f"{COLOR_RED}This Cloudera Manager does not have a "
              f"{BANNER_PARAMETER} parameter, so there is no banner to write."
              f"{COLOR_TERMINATION}")
        return EXIT_ERROR
    current_value = configuration[BANNER_PARAMETER]
    new_value = replace_block(current_value, block)
    if new_value == (current_value or ""):
        print(f"{COLOR_CYAN}The banner of Cloudera Manager already says this."
              f"{COLOR_TERMINATION}")
        return EXIT_CLEAN
    print(f"{COLOR_CYAN}Banner:{COLOR_TERMINATION} {new_value or '(empty)'}")
    if dry_run:
        print(f"{COLOR_YELLOW}Not written, as this was a dry run."
              f"{COLOR_TERMINATION}")
        return EXIT_CLEAN
    if not api.put_cm_config(BANNER_PARAMETER, new_value):
        print(f"{COLOR_RED}Could not write the banner. Writing the Cloudera "
              f"Manager configuration requires the Full Administrator role."
              f"{COLOR_TERMINATION}")
        return EXIT_ERROR
    print(f"{COLOR_CYAN}The banner of Cloudera Manager was updated."
          f"{COLOR_TERMINATION}")
    return EXIT_CLEAN


def main(argv: Optional[List[str]] = None) -> int:
    """
    The entry point of `coguard-cloudera-banner`.
    """
    args = argument_parser().parse_args(argv)
    apply_logging_level(args)
    credentials = resolve_credentials(args)
    if not credentials:
        return EXIT_ERROR
    api = connect_for_writing(credentials)
    if api is None:
        return EXIT_ERROR
    # Which cluster the findings are about is worth naming in a header that is
    # shown for the whole Cloudera Manager instance, so it is asked for rather
    # than only taken from the option.
    block = determine_block(
        args,
        determine_cluster_name(api, credentials.get("cluster"))
    )
    if block is None:
        return EXIT_ERROR
    return write_banner(api, block, args.dry_run)

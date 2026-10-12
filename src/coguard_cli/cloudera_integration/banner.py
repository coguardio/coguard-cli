"""
The `coguard-cloudera-banner` entry point.

It takes the result of a scan and puts a summary of it into the header of
Cloudera Manager, so that the state of the configuration is visible to the people
who administer the cluster in the place where they administer it, rather than
only in a portal they have to remember to open.

The parameter written is `CUSTOM_BANNER_HTML` of the Cloudera Manager service
configuration, which Cloudera provides for exactly this purpose ("The custom
banner is used to display customer specific text in the header area."). Three
consequences follow from what that parameter actually is, and they are what most
of this module is about:

* **What goes in is plain text, in spite of the name of the parameter.**
  Cloudera Manager 7.13 escapes the value and shows it verbatim, so a `<span>`
  put around the text appears in the header as a `<span>`. Cloudera's own
  validation calls it "the Custom Banner Text parameter", and plain text is in
  any case the only form which survives both behaviours: a version which escapes
  the value shows it as written, and a version which renders it shows it as well.
  What is given up is the colour, so the wording has to carry the severity on its
  own. Values taken from the result still have `<` and `>` removed, so that they
  cannot turn into markup on a version which does render the value.
* **The banner is shared.** A customer may already display something in it, a
  maintenance notice or the name of the environment, and that text is not ours to
  remove. The current value is therefore read before it is written, and only the
  region from `CoGuard:` to the end of the value is replaced, which keeps
  whatever is in front of it. The delimiter is the visible text rather than an
  HTML comment for the reason above: a comment is not invisible in a value which
  is escaped. A block left behind by the earlier, HTML version is recognised by
  its delimiters and removed.
* **It has to stay short.** It is a header, not a report. Only the counts and
  the worst affected services are shown, capped by `--max-services`, and the
  detail stays in the report the banner points to.

The colour the banner text cannot have is available one level up, in the header
bar the banner sits in: `CUSTOM_HEADER_COLOR` is what Cloudera Manager tints it
with. With `--header-color`, the bar is red while there are findings and back to
its ordinary colour once there are none, which is the difference between a line
of text somebody may read and a page nobody can open without noticing. It is off
by default, because that parameter exists to tell instances of Cloudera Manager
apart and a customer may be using it for that -- which is also why the colour is
put back only when it is still the one this command set.

This is the one part of the Cloudera integration which changes the cluster. The
client used for scanning issues `GET` requests only, on purpose, so the single
`PUT` lives in `ClouderaManagerBannerApi` in this module, which is used by
nothing else. Writing the Cloudera Manager service configuration requires the
Full Administrator role, unlike the read-only scan, so this command is meant to
be given a credential of its own rather than the one the scan uses.
"""

import argparse
import datetime
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
# The parameter holding the colour of the header bar itself, which is the one
# thing in the header that *can* carry a severity, since the banner text cannot.
# Cloudera provides it to "distinguish different instances of Cloudera Manager",
# so it is written only when asked for with `--header-color`.
HEADER_COLOR_PARAMETER = "CUSTOM_HEADER_COLOR"
# The values that parameter accepts. The API does not publish them -- not one of
# the 282 parameters of the resource comes with `validValues` -- and they are not
# in the documentation either, so they were read off the assets the header is
# built from: Cloudera Manager ships one `favicon-<COLOUR>.png` per value, and
# these ten exist.
HEADER_COLORS = (
    "BLACK",
    "GRAY",
    "RED",
    "YELLOW",
    "GREEN",
    "TEAL",
    "BLUE",
    "PURPLE",
    "PINK",
    "BROWN",
)
# What the header is set back to once the findings are gone. `BLACK` is Cloudera
# Manager's own default for the parameter.
DEFAULT_HEADER_COLOR_CLEAN = "BLACK"
# Where the region of the banner this command owns begins. It runs from here to
# the end of the value; everything in front of it belongs to whoever put it there
# and is preserved verbatim.
BLOCK_MARKER = "CoGuard:"
# What separates an existing banner from the region written here.
SEPARATOR = " | "
# The delimiters an earlier version of this command wrote around its region, when
# the banner was built as HTML. They are still recognised so that a cluster which
# has such a banner gets it replaced rather than kept as visible markup.
LEGACY_BLOCK_START = "<!--coguard:start-->"
LEGACY_BLOCK_END = "<!--coguard:end-->"
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

    def put_cm_config(self, values: Dict[str, str]) -> bool:
        """
        Sets parameters of the Cloudera Manager service configuration.

        This is the only request in the whole integration which is not a `GET`.
        A partial update is sent, i.e. the request names only the parameters to
        change, which is how Cloudera Manager expects it and what keeps the other
        280 parameters of the resource out of the picture entirely.

        All of them go into one request, because one request is one configuration
        revision: writing the banner and the header colour separately would
        appear in the event feed, and in the audit trail of the cluster, as two
        changes where an operator made none.
        """
        url = self._api_url("cm", "config")
        logging.debug("Writing %s through %s", ", ".join(values), url)
        try:
            response = self._session.put(
                url,
                json={"items": [{"name": name, "value": value}
                                for name, value in values.items()]},
                timeout=self._timeout
            )
            response.raise_for_status()
        except requests.RequestException as err:
            logging.error("Could not write %s: %s", ", ".join(values), err)
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


def plain(value: str) -> str:
    """
    A value from the scan result in the form it can go into the banner: on one
    line, and without the two characters which would make it markup on a version
    of Cloudera Manager which renders the banner rather than escaping it.

    Removing those characters rather than escaping them is what keeps the text
    readable in both cases. `&lt;` in an escaped banner is what a service name
    escaped for HTML looks like when it is not rendered, and no name of a real
    service, cluster or file contains `<` to begin with.
    """
    return " ".join(str(value).split()).replace("<", "").replace(">", "")


def render_block(findings: List[Dict],
                 cluster_name: Optional[str],
                 report_url: Optional[str],
                 max_services: int) -> str:
    """
    Renders the region of the banner this command owns, as one line of plain
    text beginning with the marker.

    There is no colour to signal with, so the first thing the line says is
    whether there are findings or not.
    """
    scanned_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    where = f" of {plain(cluster_name)}" if cluster_name else ""
    if not findings:
        headline = (
            f"{BLOCK_MARKER} the configuration{where} has no findings "
            f"(scanned {scanned_at})."
        )
    else:
        buckets, services = summarize(findings)
        counts = ", ".join(f"{count} {name}" for name, count in buckets)
        shown = services[:max_services]
        named = ", ".join(
            f"{plain(service)} ({count})" for service, count in shown
        )
        remaining = len(services) - len(shown)
        if remaining > 0:
            named += f" and {remaining} further service" \
                     f"{'s' if remaining > 1 else ''}"
        headline = (
            f"{BLOCK_MARKER} {len(findings)} configuration finding"
            f"{'s' if len(findings) > 1 else ''}{where} ({counts}), affecting "
            f"{named}. Scanned {scanned_at}."
        )
    if report_url:
        # Not clickable, since the banner is text. It is still worth showing:
        # an address can be copied, and where the detail is kept is part of what
        # the header has to say.
        headline += f" Full report: {plain(report_url)}"
    return headline


def without_legacy_block(current: str) -> str:
    """
    Removes the region an earlier, HTML version of this command wrote, so that a
    banner which still holds one is not left with visible markup in front of the
    new text.

    A banner whose start delimiter has no end delimiter after it was written by
    an interrupted run of that version. Everything from the delimiter onwards is
    then ours and is dropped, since what came before it is the part that belongs
    to somebody else.
    """
    start = current.find(LEGACY_BLOCK_START)
    if start < 0:
        return current
    end = current.find(LEGACY_BLOCK_END, start + len(LEGACY_BLOCK_START))
    after = current[end + len(LEGACY_BLOCK_END):] if end > start else ""
    return f"{current[:start].rstrip()} {after.strip()}".strip()


def replace_block(current_value: Optional[str], block: str) -> str:
    """
    Puts a block into the current banner, replacing an earlier one of ours and
    keeping the text in front of it. An empty block removes the region entirely.

    The region owned here runs from the marker to the end of the value, i.e. this
    command writes last. Text a customer put in the banner therefore survives, and
    what is given up in exchange for a delimiter that is not visible in an escaped
    banner is the ability to keep text placed *after* ours.
    """
    current = without_legacy_block(current_value or "")
    start = current.find(BLOCK_MARKER)
    before = (current[:start] if start >= 0 else current).rstrip()
    # A banner this command wrote before is removed together with the separator
    # it was joined on, so that repeated runs do not leave a dangling one.
    before = before.rstrip(SEPARATOR.strip()).rstrip()
    if not block:
        return before
    separator = SEPARATOR if before else ""
    return f"{before}{separator}{block}"


def argument_parser() -> argparse.ArgumentParser:
    """
    The command line of `coguard-cloudera-banner`.
    """
    parser = argparse.ArgumentParser(
        prog="coguard-cloudera-banner",
        description=(
            "Show the result of a CoGuard scan in the header of Cloudera "
            "Manager. Only the part of the banner from `CoGuard:` onwards is "
            "written, so an existing banner is kept."
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
        '--header-color',
        type=str.upper,
        dest='header_color',
        choices=HEADER_COLORS,
        required=False,
        help=("Also colour the header bar of Cloudera Manager in this colour "
              "while there are findings, and set it back to the colour of "
              "`--header-color-clean` once there are none. The header is not "
              "touched at all unless this is given.")
    )
    parser.add_argument(
        '--header-color-clean',
        type=str.upper,
        dest='header_color_clean',
        choices=HEADER_COLORS,
        default=DEFAULT_HEADER_COLOR_CLEAN,
        required=False,
        help=(f"The colour to put the header bar back to once there are no "
              f"findings. Defaults to {DEFAULT_HEADER_COLOR_CLEAN}, which is "
              f"Cloudera Manager's own default; set it to the colour this "
              f"instance is normally recognised by, if it has one.")
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        dest='clear',
        default=False,
        required=False,
        help=("Remove the CoGuard region from the banner, and put the header "
              "colour back if `--header-color` says which one this command "
              "sets. No scan result is read.")
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
                    cluster_name: Optional[str]
                    ) -> Optional[Tuple[str, bool]]:
    """
    Produces the block to put into the banner, which is empty when the region is
    to be removed, together with whether there are findings. `None` means the
    result could not be read, and nothing should be written.
    """
    if args.clear:
        return "", False
    result = read_result(args.result_file)
    if result is None:
        return None
    findings = failed_findings(result, args.minimum_severity)
    return render_block(
        findings,
        cluster_name,
        args.report_url,
        max(1, args.max_services)
    ), bool(findings)


def desired_header_color(args: argparse.Namespace,
                         has_findings: bool,
                         current: Optional[str]) -> Optional[str]:
    """
    The colour the header bar is to have, or `None` for leaving it as it is.

    While there are findings, it is the colour that was asked for. Once there are
    none, it is put back -- but only if it currently is the colour this command
    sets, so that a header which somebody else coloured, to tell this instance of
    Cloudera Manager apart from another one, is not quietly taken over by a
    scan which found nothing.
    """
    if not args.header_color:
        return None
    if has_findings:
        return args.header_color
    if (current or "").strip().upper() == args.header_color:
        return args.header_color_clean
    return None


def write_banner(api: ClouderaManagerBannerApi,
                 block: str,
                 has_findings: bool,
                 args: argparse.Namespace) -> int:
    """
    Puts a block into the banner of Cloudera Manager, and the matching colour
    into its header if one was asked for, leaving whatever else is in the banner
    alone. Returns the exit code of doing so.
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
    changes: Dict[str, str] = {}
    if new_value != (current_value or ""):
        changes[BANNER_PARAMETER] = new_value
        print(f"{COLOR_CYAN}Banner:{COLOR_TERMINATION} {new_value or '(empty)'}")
    if args.header_color and HEADER_COLOR_PARAMETER not in configuration:
        # Not an error: the banner is what this command is for, and a release
        # without the parameter still gets it.
        print(f"{COLOR_YELLOW}This Cloudera Manager does not have a "
              f"{HEADER_COLOR_PARAMETER} parameter, so the header keeps its "
              f"colour.{COLOR_TERMINATION}")
    elif args.header_color:
        # An unset parameter is Cloudera Manager's default rather than no colour.
        current_color = configuration[HEADER_COLOR_PARAMETER] \
            or DEFAULT_HEADER_COLOR_CLEAN
        new_color = desired_header_color(args, has_findings, current_color)
        if new_color is not None and new_color != current_color:
            changes[HEADER_COLOR_PARAMETER] = new_color
            print(f"{COLOR_CYAN}Header colour:{COLOR_TERMINATION} "
                  f"{current_color} -> {new_color}")
    if not changes:
        print(f"{COLOR_CYAN}The header of Cloudera Manager already says this."
              f"{COLOR_TERMINATION}")
        return EXIT_CLEAN
    if args.dry_run:
        print(f"{COLOR_YELLOW}Not written, as this was a dry run."
              f"{COLOR_TERMINATION}")
        return EXIT_CLEAN
    if not api.put_cm_config(changes):
        print(f"{COLOR_RED}Could not write the header. Writing the Cloudera "
              f"Manager configuration requires the Full Administrator role."
              f"{COLOR_TERMINATION}")
        return EXIT_ERROR
    print(f"{COLOR_CYAN}The header of Cloudera Manager was updated."
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
    determined = determine_block(
        args,
        determine_cluster_name(api, credentials.get("cluster"))
    )
    if determined is None:
        return EXIT_ERROR
    block, has_findings = determined
    return write_banner(api, block, has_findings, args)

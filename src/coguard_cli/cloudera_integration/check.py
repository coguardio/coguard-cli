"""
The `coguard-cloudera-check` entry point.

It asks Cloudera Manager whether anything has happened to a cluster which
changes its configuration, and runs `coguard cloud cloudera` when it has. The
point is that the configuration of a Cloudera cluster is not a thing which
changes on a schedule: it changes when somebody changes it, and a scan is worth
running then.

One invocation performs exactly one check. When and how often that happens is
the business of a systemd timer, a cron job or a CI schedule, not of this
program: those already know how to catch up after downtime, spread a fleet out
over an interval, restart on failure and log where an operator looks.

What is asked is the event feed of Cloudera Manager,

    GET /api/{version}/events?query=attributes.EVENTCODE==EV_REVISION_CREATED

whose entries name the change itself:

    content: "User admin created a new revision. Message was: Setting the value
              of ozone_security_enabled to true."
    attributes: REVISION, USER, CLUSTER, SERVICE, SERVICE_TYPE, ROLE,
                ROLE_CONFIG_GROUP, EVENTCODE, URL

`EV_REVISION_CREATED` is the configuration change, and the restart codes are the
moment it takes effect, i.e. the moment the generated configuration files on the
hosts become the ones actually in force. Both are worth a scan, and both are in
`WATCHED_EVENT_CODES`.

The audit feed, `GET /audits`, is deliberately *not* what is asked here. It
records operations -- logins, commands, the creation of services, roles and
hosts -- and not the values of configuration parameters, so a change to a
parameter of a running service leaves no trace in it.

What cannot be moved out of this program is the memory of how far the event feed
has already been read, which is what the state file holds: the events resource
has no server side time filter (`timeOccurred` is not a queryable attribute, and
`from` and `to` are accepted but ignored), so the watermark has to be kept by the
caller.

The event feed is a change *hint*, not a guarantee: events are retained for a
finite time, the Event Server can be down, and CoGuard adds rules over time. This
is why a scan is also run once the previous one is older than
`--maximum-scan-age`. That periodic scan is what bounds how long the report can
be out of date.
"""

import argparse
import datetime
import json
import logging
import os
import pathlib
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from coguard_cli.cloudera_integration import EXIT_CLEAN, EXIT_ERROR, \
    add_cloudera_manager_arguments, apply_logging_level, connect, \
    resolve_credentials
from coguard_cli.discovery.cloudera_discovery import determine_cluster_name
from coguard_cli.discovery.cloudera_discovery.cloudera_manager_api import \
    ClouderaManagerApi, DEFAULT_EVENT_PAGE_SIZE, event_attribute
from coguard_cli.print_colors import COLOR_CYAN, COLOR_RED, \
    COLOR_TERMINATION, COLOR_YELLOW

# The events which mean that the configuration of the cluster is, or is about to
# be, a different one than at the last check. `EV_REVISION_CREATED` is the change
# to a configuration parameter, the restart codes are the point at which a change
# reaches the running processes, the creation codes are a service or role which
# was not there before, and `EV_PARCEL_ACTIVATE` is a new software version, whose
# generated configuration files are new as well.
#
# An event code Cloudera Manager does not know is not an error: the query simply
# matches nothing. A code which is missing from this list, on the other hand, is
# a change which goes unnoticed until the next periodic scan, which is why
# `--event-code` exists.
WATCHED_EVENT_CODES = (
    "EV_REVISION_CREATED",
    "EV_CLUSTER_RESTARTED",
    "EV_SERVICE_RESTARTED",
    "EV_ROLE_RESTARTED",
    "EV_SERVICE_CREATED",
    "EV_SERVICE_DELETED",
    "EV_ROLE_CREATED",
    "EV_ROLE_DELETED",
    "EV_HOST_TEMPLATE_APPLIED",
    "EV_PARCEL_ACTIVATE"
)
DEFAULT_STATE_FILE = str(pathlib.Path.home().joinpath(
    '.config',
    'coguard-cli',
    'cloudera_check_state.json'
))
# A rolling restart moves the state of one service after the other, and a scan
# takes minutes. Without a lower bound on the distance between two scans, a
# restart of the cluster would result in a scan per service.
DEFAULT_MINIMUM_SCAN_INTERVAL = 900
DEFAULT_MAXIMUM_SCAN_AGE = 86400
# How many events are named in the log line stating why a scan is being run. A
# configuration change of a service commonly produces one event per parameter.
MAXIMUM_DESCRIBED_EVENTS = 5
# Stands in for the timestamp of an event whose own one cannot be read, so that
# such an event sorts last rather than making the sort fail.
EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def argument_parser() -> argparse.ArgumentParser:
    """
    The argument parser of this entry point.
    """
    parser = argparse.ArgumentParser(
        prog="coguard-cloudera-check",
        description=("Check whether the configuration of a Cloudera cluster has "
                     "changed, and scan it with CoGuard if it has. Performs one "
                     "check; run it from a systemd timer or a cron job.")
    )
    add_cloudera_manager_arguments(parser)
    parser.add_argument(
        '--event-code',
        type=str,
        dest='event_codes',
        action='append',
        required=False,
        help=(f"A Cloudera Manager event code which is to be treated as a "
              f"configuration change. May be given more than once, and replaces "
              f"the default set of {', '.join(WATCHED_EVENT_CODES)}.")
    )
    parser.add_argument(
        '--minimum-scan-interval',
        type=int,
        dest='minimum_scan_interval',
        default=DEFAULT_MINIMUM_SCAN_INTERVAL,
        help=(f"The number of seconds a scan is at least apart from the "
              f"previous one, so that a rolling restart does not result in a "
              f"scan per service. Defaults to "
              f"{DEFAULT_MINIMUM_SCAN_INTERVAL}.")
    )
    parser.add_argument(
        '--maximum-scan-age',
        type=int,
        dest='maximum_scan_age',
        default=DEFAULT_MAXIMUM_SCAN_AGE,
        help=(f"The number of seconds after which a scan is run even though no "
              f"event reported a change. Defaults to "
              f"{DEFAULT_MAXIMUM_SCAN_AGE}.")
    )
    parser.add_argument(
        '--state-file',
        type=str,
        dest='state_file',
        default=DEFAULT_STATE_FILE,
        help=(f"The file the position in the event feed and the outcome of the "
              f"last scan are remembered in. Defaults to {DEFAULT_STATE_FILE}.")
    )
    parser.add_argument(
        '--minimum-fail-level',
        type=int,
        dest='fail_level',
        required=False,
        help=("The minimum severity of a finding for the scan to exit with a "
              "non-zero exit code. Passed on to `coguard`, which defaults to 1, "
              "i.e. any finding.")
    )
    parser.add_argument(
        '--coguard-cli',
        type=str,
        dest='coguard_cli',
        default="coguard",
        help="The CoGuard CLI executable to perform the scans with."
    )
    parser.add_argument(
        '--ruleset',
        type=str,
        dest='ruleset',
        required=False,
        help=("The compliance rule set to scan against, e.g. `nist800-53`. "
              "Requires an enterprise subscription.")
    )
    parser.add_argument(
        '--coguard-api-url',
        type=str,
        dest='coguard_api_url',
        required=False,
        help="The url of the CoGuard api to call."
    )
    parser.add_argument(
        '--coguard-auth-url',
        type=str,
        dest='coguard_auth_url',
        required=False,
        help="The url of the CoGuard authentication server."
    )
    return parser


def now() -> str:
    """
    The current point in time, as it is recorded in the state file.
    """
    return datetime.datetime.now(
        datetime.timezone.utc
    ).replace(microsecond=0).isoformat()


def parse_timestamp(timestamp: Optional[str]) -> Optional[datetime.datetime]:
    """
    Reads a timestamp of the state file or of an event. Cloudera Manager reports
    the latter as `2026-09-04T16:20:37.738Z`, whose trailing `Z` older Python
    versions do not accept.
    """
    if not timestamp:
        return None
    candidate = timestamp.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(candidate)
    except (TypeError, ValueError):
        logging.warning("Could not read the timestamp `%s`.", timestamp)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def seconds_since(timestamp: Optional[str]) -> Optional[float]:
    """
    The number of seconds which have passed since a timestamp of the state file,
    or `None` if there is no usable timestamp.
    """
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return None
    return (datetime.datetime.now(datetime.timezone.utc) - parsed) \
        .total_seconds()


def is_newer(candidate: Optional[str], reference: Optional[str]) -> bool:
    """
    States whether one timestamp is newer than another one. A timestamp which
    cannot be read counts as newer, so that an unreadable one results in a scan
    rather than in a change which is silently skipped.
    """
    reference_time = parse_timestamp(reference)
    if reference_time is None:
        return True
    candidate_time = parse_timestamp(candidate)
    if candidate_time is None:
        return True
    return candidate_time > reference_time


def read_state(state_file: str) -> Dict:
    """
    Reads the state of the previous check. A state file which does not exist or
    cannot be read results in an empty state, i.e. in a scan.
    """
    try:
        return json.loads(
            pathlib.Path(state_file).read_text(encoding='utf-8')
        ) or {}
    except FileNotFoundError:
        logging.debug("No state file at %s yet.", state_file)
        return {}
    except (OSError, ValueError) as err:
        logging.warning("Could not read the state file %s: %s", state_file, err)
        return {}


def write_state(state_file: str, state: Dict) -> None:
    """
    Stores the state for the next check. Being unable to do so is reported, but
    does not fail the check: it means the next one has no watermark and scans,
    which is the safe direction.
    """
    try:
        path = pathlib.Path(state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding='utf-8')
    except OSError as err:
        logging.warning("Could not write the state file %s: %s",
                        state_file,
                        err)


def event_cluster(event: Dict) -> Optional[str]:
    """
    The cluster an event belongs to, or `None` for an event which is not about a
    single cluster, such as the activation of a parcel or a change to the
    configuration of Cloudera Manager itself.
    """
    return event_attribute(event, "CLUSTER") \
        or event_attribute(event, "CLUSTER_DISPLAY_NAME")


def describe_event(event: Dict) -> str:
    """
    States an event in words, so that the log of the check says what it reacted
    to. The `content` of an event already is a sentence naming the parameter and
    its new value; what it does not name is the service it belongs to.
    """
    service = event_attribute(event, "SERVICE_DISPLAY_NAME") \
        or event_attribute(event, "SERVICE")
    content = (event.get("content") or "").strip() \
        or event_attribute(event, "EVENTCODE") \
        or "an event without a description"
    return f"{service}: {content}" if service else content


def event_time(event: Dict) -> datetime.datetime:
    """
    The point in time an event occurred, for ordering a list of events.
    """
    return parse_timestamp(event.get("timeOccurred")) or EPOCH


def describe_events(events: List[Dict]) -> str:
    """
    States the events which led to a scan in words, naming at most
    `MAXIMUM_DESCRIBED_EVENTS` of them.
    """
    described = [describe_event(event)
                 for event in events[:MAXIMUM_DESCRIBED_EVENTS]]
    remaining = len(events) - len(described)
    if remaining > 0:
        described.append(f"and {remaining} further event(s)")
    return " ".join(described)


def poll_events(api: ClouderaManagerApi,
                cluster_name: str,
                event_codes: List[str],
                watermark: Optional[str]) -> Optional[Dict]:
    """
    Asks Cloudera Manager for the newest events of each watched code and returns
    the ones which are newer than the watermark and belong to this cluster,
    together with the newest timestamp seen and whether the answer was a full
    page.

    `None` is returned if Cloudera Manager did not answer, which is a failure to
    look rather than a cluster which did not change.

    One request per event code is issued instead of one request for the whole
    audit category, because the events resource answers with a bounded page and
    only the newest matching entries. Per code, the newest matching event is
    therefore always in the answer, whereas in a shared page the events of one
    busy code -- a login is an audit event too -- could push another code out of
    it.
    """
    events = []
    newest = watermark
    truncated = False
    for event_code in event_codes:
        items = api.list_events(f"attributes.EVENTCODE=={event_code}")
        if items is None:
            logging.error("Cloudera Manager did not answer for the event code "
                          "%s.", event_code)
            return None
        oldest_returned = min(items, key=event_time).get("timeOccurred") \
            if items else None
        if len(items) >= DEFAULT_EVENT_PAGE_SIZE \
           and is_newer(oldest_returned, watermark):
            # The answer is a full page which does not reach back to the
            # watermark, so there are events in between which were not returned.
            logging.info("There are more than %d events of the code %s which "
                         "have not been looked at yet.",
                         DEFAULT_EVENT_PAGE_SIZE,
                         event_code)
            truncated = True
        for item in items:
            timestamp = item.get("timeOccurred")
            if parse_timestamp(timestamp) is not None \
               and is_newer(timestamp, newest):
                newest = timestamp
            if not is_newer(timestamp, watermark):
                continue
            cluster = event_cluster(item)
            if cluster is not None and cluster != cluster_name:
                continue
            events.append(item)
    events.sort(key=event_time, reverse=True)
    return {"events": events, "newest": newest, "truncated": truncated}


def scan_reason(state: Dict,
                poll_result: Dict,
                maximum_scan_age: int) -> Optional[str]:
    """
    Decides whether a scan is to be run, and states why.
    """
    if not state.get("lastEventAt"):
        return ("the event feed of this cluster has not been read before, so "
                "there is no position in it to compare against")
    if poll_result["events"]:
        return describe_events(poll_result["events"])
    if poll_result["truncated"]:
        return ("Cloudera Manager answered with a full page of events, so it "
                "cannot be ruled out that a change is among the ones which were "
                "not returned")
    scan_age = seconds_since(state.get("lastScanAt"))
    if scan_age is None:
        return "no scan has been recorded yet"
    if maximum_scan_age and scan_age >= maximum_scan_age:
        return (f"the last scan is {int(scan_age)} seconds old, and a scan is "
                f"due every {maximum_scan_age} seconds")
    return None


def build_cli_arguments(args: argparse.Namespace,
                        credentials: Dict,
                        cluster_name: str) -> List[str]:
    """
    Assembles the `coguard cloud cloudera` command line which performs the scan.

    The options of the CLI itself precede the sub-command and the connection
    parameters follow it. The connection parameters are the ones which have
    already been resolved here, so that the scan does not resolve them a second
    time and cannot end up asking for a password. The password is not among
    them; it is handed over through the environment.
    """
    arguments = [
        args.coguard_cli,
        "--logging-level", str(args.logging_level)
    ]
    for option, value in (("--minimum-fail-level", args.fail_level),
                          ("--ruleset", args.ruleset),
                          ("--coguard-api-url", args.coguard_api_url),
                          ("--coguard-auth-url", args.coguard_auth_url)):
        if value is not None:
            arguments.extend([option, str(value)])
    arguments.extend(["cloud", "cloudera"])
    for option, value in (
            ("--cloudera-manager-url", credentials.get("url")),
            ("--cloudera-manager-user", credentials.get("username")),
            ("--cloudera-manager-ca-cert", credentials.get("ca_cert")),
            ("--cloudera-cluster", cluster_name)):
        if value:
            arguments.extend([option, str(value)])
    if not credentials.get("verify_tls", True):
        arguments.append("--cloudera-manager-no-verify-tls")
    return arguments


def run_scan(arguments: List[str],
             environment: Optional[Dict[str, str]] = None) -> Optional[int]:
    """
    Runs the CoGuard CLI and returns its exit code, or `None` if it could not be
    run at all, which is not the same thing as a scan which found something.
    """
    if not shutil.which(arguments[0]):
        print(f"{COLOR_RED}The CoGuard CLI `{arguments[0]}` was not found. "
              f"Install it with `pip install coguard-cli`, or point "
              f"`--coguard-cli` at it.{COLOR_TERMINATION}")
        return None
    logging.debug("Running %s", " ".join(arguments))
    completed = subprocess.run(
        arguments,
        env=dict(os.environ, **(environment or {})),
        check=False
    )
    return completed.returncode


def perform_check(api: ClouderaManagerApi,
                  cluster_name: str,
                  args: argparse.Namespace,
                  credentials: Dict,
                  state: Dict) -> Tuple[Dict, int]:
    """
    Performs the check, runs a scan if the cluster calls for one, and returns the
    new state together with the exit code of this program.
    """
    state = dict(state)
    state["cluster"] = cluster_name
    state["lastCheckedAt"] = now()
    poll_result = poll_events(
        api,
        cluster_name,
        args.event_codes or list(WATCHED_EVENT_CODES),
        state.get("lastEventAt")
    )
    if poll_result is None:
        print(f"{COLOR_RED}Could not read the events of the cluster "
              f"{cluster_name} from Cloudera Manager.{COLOR_TERMINATION}")
        return (state, EXIT_ERROR)
    reason = scan_reason(state, poll_result, args.maximum_scan_age)
    if reason is None:
        print(f"{COLOR_CYAN}Nothing has changed the configuration of "
              f"{COLOR_TERMINATION}{cluster_name}{COLOR_CYAN}. Not scanning."
              f"{COLOR_TERMINATION}")
        state["lastEventAt"] = poll_result["newest"]
        return (state, EXIT_CLEAN)
    scan_age = seconds_since(state.get("lastScanAt"))
    if scan_age is not None and scan_age < args.minimum_scan_interval:
        # The watermark is deliberately not advanced here, so that the change
        # which is being postponed is still a change at the next check.
        print(f"{COLOR_YELLOW}Postponing the scan of {cluster_name}: the "
              f"previous one was {int(scan_age)} seconds ago, and scans are at "
              f"least {args.minimum_scan_interval} seconds apart."
              f"{COLOR_TERMINATION}")
        return (state, EXIT_CLEAN)
    print(f"{COLOR_CYAN}Scanning {cluster_name}, because "
          f"{COLOR_TERMINATION}{reason}")
    exit_code = run_scan(
        build_cli_arguments(args, credentials, cluster_name),
        {"CLOUDERA_MANAGER_PASSWORD": credentials.get("password", "")}
    )
    if exit_code is None:
        # No scan happened, so the watermark is not advanced either and the
        # change is still pending at the next check.
        return (state, EXIT_ERROR)
    state["lastEventAt"] = poll_result["newest"]
    state["lastScanAt"] = now()
    state["lastScanReason"] = reason
    state["lastScanExitCode"] = exit_code
    return (state, exit_code)


def main(argv: Optional[List[str]] = None) -> int:
    """
    The entry point of `coguard-cloudera-check`.
    """
    args = argument_parser().parse_args(argv)
    apply_logging_level(args)
    credentials = resolve_credentials(args)
    if not credentials:
        return EXIT_ERROR
    api = connect(credentials)
    if api is None:
        return EXIT_ERROR
    cluster_name = determine_cluster_name(api, credentials.get("cluster"))
    if not cluster_name:
        print(f"{COLOR_RED}Could not determine which cluster to check."
              f"{COLOR_TERMINATION}")
        return EXIT_ERROR
    state = read_state(args.state_file)
    if state.get("cluster") and state.get("cluster") != cluster_name:
        logging.info("The state file describes the cluster %s. Starting over "
                     "for %s.", state.get("cluster"), cluster_name)
        state = {}
    state, exit_code = perform_check(
        api, cluster_name, args, credentials, state
    )
    write_state(args.state_file, state)
    return exit_code

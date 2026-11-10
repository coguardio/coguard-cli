#!/usr/bin/env bash
#
# The process Cloudera Manager supervises for the Configuration Check role.
#
# A custom service descriptor cannot declare a health test. There is no such
# field in the schema -- neither the service nor the role descriptor has one, and
# the metric definitions of an MDL have no thresholds -- so the one health signal
# a CSD can move is whether its own role process is running. This script
# therefore *is* the signal: it stays alive while the scans of the cluster come
# back clean, and exits non-zero once one reports findings at or above the
# configured severity. Cloudera Manager reports that as a role which exited
# unexpectedly, which is what turns the badge of this service red and the health
# of the cluster bad.
#
# Two consequences of that mechanism, both of them also in ../README.md:
#
#   * While this service is red, nothing is scanning any more, because the
#     process which would scan is the one that exited. The badge does not go
#     green by itself once the configuration is fixed; restarting the role is
#     what re-checks. The first check after a start therefore ignores the
#     minimum scan interval -- a restart is somebody asking for a fresh look.
#   * The exit code of the check command is not the health of the cluster. It is
#     0 both for "scanned, nothing found" and for "no scan was due", and a scan
#     which fails inside the CLI is a 1 as well. What the health is read from is
#     the outcome of the last scan, which the check records in its state file.
#
# The CoGuard CLI comes from the COGUARD parcel, which the descriptor requires:
# the agent sources the parcel's meta/coguard_env.sh before starting this script,
# which sets COGUARD_HOME and puts the parcel's bin/ on the PATH.
#
# Everything this needs is in the environment, put there by the startRunner of
# the descriptor, the passwords included: they are password parameters, which
# Cloudera Manager redacts in its API, its web interface and its exports. A
# credentials file named by ENVIRONMENT_FILE can supply them instead.

set -u

readonly EXIT_CLEAN=0
readonly EXIT_FINDINGS=1
readonly EXIT_ERROR=2

# The command line of the check, assembled by `check_options`. It is a global
# because an array cannot be returned from a function, and passing one by
# reference needs a bash newer than the one on some of the hosts this runs on.
CHECK_ARGUMENTS=()

log() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

# A stop or a restart asked for by Cloudera Manager arrives as a signal, and has
# to look like an orderly end rather than like a cluster with findings.
terminate() {
    log "A stop was requested. Ending the configuration check."
    exit "${EXIT_CLEAN}"
}
trap terminate TERM INT

# Waits, but stays interruptible: a `sleep` in the foreground would delay a stop
# by up to a whole check interval, because a signal handler only runs once the
# command in the foreground has finished.
interruptible_sleep() {
    sleep "$1" &
    wait $!
}

# The configuration of this role, as the descriptor hands it over. Every value
# has the default of the parameter it belongs to, so that a Cloudera Manager
# which leaves an empty parameter out of the environment is not a crash with an
# unbound variable but the documented default.
read_configuration() {
    CLOUDERA_MANAGER_URL=${CLOUDERA_MANAGER_URL:-}
    CLOUDERA_MANAGER_USER=${CLOUDERA_MANAGER_USER:-coguard}
    CLOUDERA_MANAGER_CA_CERT=${CLOUDERA_MANAGER_CA_CERT:-}
    CLOUDERA_CLUSTER=${CLOUDERA_CLUSTER:-}
    ENVIRONMENT_FILE=${ENVIRONMENT_FILE:-}
    MINIMUM_FAIL_LEVEL=${MINIMUM_FAIL_LEVEL:-4}
    RULESET=${RULESET:-}
    CHECK_EXECUTABLE=${CHECK_EXECUTABLE:-coguard-cloudera-check}
    COGUARD_EXECUTABLE=${COGUARD_EXECUTABLE:-coguard}
    PYTHON_EXECUTABLE=${PYTHON_EXECUTABLE:-coguard-python}
    WORK_DIRECTORY=${WORK_DIRECTORY:-/var/lib/coguard}
    CHECK_INTERVAL_SECONDS=${CHECK_INTERVAL_SECONDS:-900}
    MINIMUM_SCAN_INTERVAL_SECONDS=${MINIMUM_SCAN_INTERVAL_SECONDS:-900}
    MAXIMUM_SCAN_AGE_SECONDS=${MAXIMUM_SCAN_AGE_SECONDS:-86400}
    ERROR_TOLERANCE=${ERROR_TOLERANCE:-3}
    STATE_FILE="${WORK_DIRECTORY}/cloudera_check_state.json"
    RESULT_FILE="${WORK_DIRECTORY}/result.json"
    if [ -z "${CLOUDERA_MANAGER_URL}" ]; then
        log "No Cloudera Manager URL is configured for this service, so there" \
            "is nothing to read the configuration of the cluster from."
        return 1
    fi
    # The parcel's environment script puts bin/ on the PATH already; this is for
    # an agent which hands over COGUARD_HOME and not the PATH it was given.
    if [ -n "${COGUARD_HOME:-}" ] && [ -d "${COGUARD_HOME}/bin" ]; then
        PATH="${COGUARD_HOME}/bin:${PATH}"
    fi
    local executable
    for executable in "${CHECK_EXECUTABLE}" "${PYTHON_EXECUTABLE}"; do
        # The interpreter is checked as well as the check command: the health
        # of this service is read with it, and one which cannot be run would
        # look like a scan that has not happened yet rather than like an error.
        if ! command -v "${executable}" > /dev/null 2>&1; then
            log "\`${executable}\` was not found on the PATH of $(id -un)." \
                "It comes from the COGUARD parcel: check that the parcel is" \
                "distributed and activated on this host, or configure an" \
                "absolute path."
            return 1
        fi
    done
    return 0
}

# Reads a file of KEY=value lines into the environment, taking every value
# verbatim. The file is deliberately not sourced: it holds passwords, and a
# password is not shell syntax -- a space, a `;` or a `$` in one would have the
# shell run the rest of it as a command and print it, part of the password
# included, into the log of this role, which Cloudera Manager shows to anybody
# who can read the logs of the service. Empty lines and lines beginning with `#`
# are skipped, and one pair of quotes around a whole value is removed, for a file
# written for `source` or for systemd. A line which is not KEY=value is reported
# by its number only, never by its content.
read_environment_file() {
    local file=$1 line key value number=0
    while IFS= read -r line || [ -n "${line}" ]; do
        number=$((number + 1))
        line=${line%$'\r'}
        case "${line}" in
            ''|'#'*) continue ;;
        esac
        key=${line%%=*}
        value=${line#*=}
        key=${key#export }
        if [ "${key}" = "${line}" ] || ! [[ "${key}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            log "Line ${number} of ${file} is not of the form KEY=value."
            return 1
        fi
        if [ "${#value}" -ge 2 ]; then
            case "${value}" in
                \"*\") value=${value:1:${#value}-2} ;;
                \'*\') value=${value:1:${#value}-2} ;;
            esac
        fi
        export "${key}=${value}"
    done < "${file}"
}

# The credentials come from the parameters of the service, which Cloudera
# Manager stores as passwords and hands to this process in its environment, and
# optionally from a credentials file, whose values take precedence. A parameter
# which was left empty arrives as an empty variable, and is treated as not set,
# so that it neither hides a value from the file nor reaches the CLI as an empty
# organization or user name.
CREDENTIAL_VARIABLES=(CLOUDERA_MANAGER_PASSWORD COGUARD_USER_NAME COGUARD_PASSWORD COGUARD_ORGANIZATION)

read_credentials() {
    local variable
    for variable in "${CREDENTIAL_VARIABLES[@]}"; do
        if [ -z "${!variable:-}" ]; then
            unset "${variable}"
        fi
    done
    if [ -n "${ENVIRONMENT_FILE}" ]; then
        if [ ! -r "${ENVIRONMENT_FILE}" ]; then
            log "The credentials file ${ENVIRONMENT_FILE} does not exist or" \
                "cannot be read by $(id -un). Leave the Credentials File" \
                "parameter empty to use the credential parameters of the" \
                "service instead."
            return 1
        fi
        # Exported, because the check hands the password on to the scan
        # through the environment, and the CLI takes the CoGuard account from
        # COGUARD_USER_NAME and COGUARD_PASSWORD, and the organization from
        # COGUARD_ORGANIZATION.
        read_environment_file "${ENVIRONMENT_FILE}" || return 1
    fi
    if [ -z "${CLOUDERA_MANAGER_PASSWORD:-}" ]; then
        log "There is no password for ${CLOUDERA_MANAGER_USER}, so there is" \
            "no way to authenticate against Cloudera Manager. Set the" \
            "Cloudera Manager Password parameter of this service."
        return 1
    fi
    if [ -z "${COGUARD_USER_NAME:-}" ] || [ -z "${COGUARD_PASSWORD:-}" ]; then
        log "There is no CoGuard account to scan with. Set the CoGuard User" \
            "and CoGuard Password parameters of this service."
        return 1
    fi
    return 0
}

# The exit code of the last scan, as the check recorded it in the state file: 0
# for a scan which found nothing, 1 for one which found something. An empty
# answer means that no scan has been recorded yet, which is not the same thing
# as a clean one.
last_scan_exit_code() {
    "${PYTHON_EXECUTABLE}" -c '
import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as state_file:
        state = json.load(state_file)
except (OSError, ValueError):
    sys.exit(0)
print(state.get("lastScanExitCode", ""))
' "${STATE_FILE}" 2>/dev/null
}

# One line saying what the last scan found, for the log of this role. The health
# test cannot carry it: what Cloudera Manager shows there is its own sentence
# about a process which exited.
#
# The summary is the one the banner command renders, so that the role log, the
# header of Cloudera Manager and the report do not each phrase the same result
# differently. An installation whose Python cannot import the CLI -- a CLI in a
# virtual environment, with `python3` outside it -- still gets the counts.
finding_summary() {
    "${PYTHON_EXECUTABLE}" -c '
import json
import sys

result_file, minimum_severity, cluster = sys.argv[1], int(sys.argv[2]), sys.argv[3]
try:
    with open(result_file, "r", encoding="utf-8") as result_stream:
        result = json.load(result_stream)
except (OSError, ValueError) as err:
    print(f"The scan result at {result_file} could not be read: {err}")
    sys.exit(0)
try:
    from coguard_cli.cloudera_integration.banner import (
        failed_findings, render_block
    )
except ImportError:
    findings = [
        entry for entry in result.get("failed", []) or []
        if isinstance(entry, dict)
        and int((entry.get("rule") or {}).get("severity", 0)) >= minimum_severity
    ]
    print(f"{len(findings)} finding(s) of severity {minimum_severity} or higher.")
else:
    print(render_block(failed_findings(result, minimum_severity),
                       cluster or None,
                       None,
                       5))
' "${RESULT_FILE}" "${MINIMUM_FAIL_LEVEL}" "${CLOUDERA_CLUSTER}" 2>/dev/null
}

# The name the last check found the cluster under in CoGuard: the name of the
# cluster in Cloudera Manager, as the check recorded it in the state file, put
# through the same function the scan names the cluster with. Empty if it cannot
# be determined, e.g. before the first check, or with an interpreter which cannot
# import the CLI.
coguard_cluster_name_of_last_check() {
    "${PYTHON_EXECUTABLE}" -c '
import json
import sys

try:
    from coguard_cli.check_common_util import replace_special_chars_with_underscore
    with open(sys.argv[1], "r", encoding="utf-8") as state_file:
        cluster = json.load(state_file).get("cluster")
except (ImportError, OSError, ValueError):
    sys.exit(0)
if cluster:
    print(replace_special_chars_with_underscore(cluster))
' "${STATE_FILE}" 2>/dev/null
}

# The CoGuard Report link of the role is put together by Cloudera Manager from
# parameters, and cannot be checked by it: a cluster name typed with a dash
# rather than an underscore is a link to a page which does not exist. This says
# so, with the value to set, rather than leaving it to the first click. It is a
# log line and not a failure, since the scan itself does not depend on it.
check_report_link() {
    local expected
    expected=$(coguard_cluster_name_of_last_check)
    if [ -z "${expected}" ]; then
        return 0
    fi
    if [ "${COGUARD_CLUSTER_NAME:-}" != "${expected}" ]; then
        log "The CoGuard Report link of this role points at the cluster" \
            "\"${COGUARD_CLUSTER_NAME:-}\", but the scan names this cluster" \
            "\"${expected}\" in CoGuard. Set the CoGuard Cluster Name" \
            "parameter of this service to ${expected} for the link to lead" \
            "to its report."
    else
        log "The report of this cluster is at" \
            "${REPORT_URL:-https://portal.coguard.io}/orgs/${COGUARD_ORGANIZATION:-}/${expected}"
    fi
}

# Writes the findings of the last scan at or above the minimum severity, as the
# CLI's markdown report, and prints it, so that it is at the end of the stdout of
# this role -- *Processes -> stdout* in Cloudera Manager, the one log of a CSD
# role its web interface links to -- just before the line saying what the health
# of the service is. The same report is the role log file declared by the
# descriptor, written anew for every scan, to a temporary name first and then
# moved over the old one, so that nobody reads half a report.
write_report() {
    local report_file="${LOG_DIR:-/var/log/configuration-assurance}/coguard-report.md"
    if ! "${PYTHON_EXECUTABLE}" -c '
import json
import pathlib
import sys

from coguard_cli.output_generators.output_generator_markdown import (
    translate_result_to_markdown
)

result_file, report_file, minimum_severity, name, report_url = sys.argv[1:6]
with open(result_file, "r", encoding="utf-8") as result_stream:
    result = json.load(result_stream)
result["failed"] = [
    entry for entry in result.get("failed", []) or []
    if isinstance(entry, dict)
    and int((entry.get("rule") or {}).get("severity", 0)) >= int(minimum_severity)
]
translate_result_to_markdown(result, name, pathlib.Path(report_file))
with open(report_file, "a", encoding="utf-8") as report:
    if not result["failed"]:
        report.write(f"\nNo findings of severity {minimum_severity} or higher.\n")
    report.write(f"\nShown are the findings of severity {minimum_severity} or higher. "
                 f"The full report: {report_url}\n")
' "${RESULT_FILE}" "${report_file}.tmp" "${MINIMUM_FAIL_LEVEL}" \
        "${COGUARD_CLUSTER_NAME:-${CLOUDERA_CLUSTER:-this cluster}}" \
        "${REPORT_URL:-https://portal.coguard.io}/orgs/${COGUARD_ORGANIZATION:-}/${COGUARD_CLUSTER_NAME:-}" \
        2>/dev/null; then
        log "The report of the last scan could not be written to ${report_file}."
        rm -f "${report_file}.tmp"
        return 0
    fi
    mv -f "${report_file}.tmp" "${report_file}"
    printf '\n%s\n' "======== CoGuard report of the last scan ========"
    cat "${report_file}"
    printf '%s\n\n' "======== End of the CoGuard report ========"
}

check_options() {
    local minimum_scan_interval=$1
    CHECK_ARGUMENTS=(
        --cloudera-manager-url "${CLOUDERA_MANAGER_URL}"
        --cloudera-manager-user "${CLOUDERA_MANAGER_USER}"
        --coguard-cli "${COGUARD_EXECUTABLE}"
        --state-file "${STATE_FILE}"
        --minimum-fail-level "${MINIMUM_FAIL_LEVEL}"
        --minimum-scan-interval "${minimum_scan_interval}"
        --maximum-scan-age "${MAXIMUM_SCAN_AGE_SECONDS}"
    )
    if [ -n "${CLOUDERA_MANAGER_CA_CERT}" ]; then
        CHECK_ARGUMENTS+=(--cloudera-manager-ca-cert "${CLOUDERA_MANAGER_CA_CERT}")
    fi
    if [ -n "${CLOUDERA_CLUSTER}" ]; then
        CHECK_ARGUMENTS+=(--cloudera-cluster "${CLOUDERA_CLUSTER}")
    fi
    if [ -n "${RULESET}" ]; then
        CHECK_ARGUMENTS+=(--ruleset "${RULESET}")
    fi
    # A CoGuard instance other than the public one. Empty means the defaults of
    # the CLI, i.e. https://portal.coguard.io.
    if [ -n "${COGUARD_API_URL:-}" ]; then
        CHECK_ARGUMENTS+=(--coguard-api-url "${COGUARD_API_URL}")
    fi
    if [ -n "${COGUARD_AUTH_URL:-}" ]; then
        CHECK_ARGUMENTS+=(--coguard-auth-url "${COGUARD_AUTH_URL}")
    fi
}

start() {
    local consecutive_errors=0
    local first_check="yes"
    local report_link_checked="no"
    local minimum_scan_interval status scan_exit_code
    log "Checking the configuration of ${CLOUDERA_CLUSTER:-this cluster}" \
        "through ${CLOUDERA_MANAGER_URL} every ${CHECK_INTERVAL_SECONDS}" \
        "seconds, and reporting a finding of severity ${MINIMUM_FAIL_LEVEL}" \
        "or higher as bad health."
    while true; do
        minimum_scan_interval="${MINIMUM_SCAN_INTERVAL_SECONDS}"
        if [ "${first_check}" = "yes" ]; then
            # Starting or restarting this role is somebody asking for a fresh
            # look, so the first check is not allowed to postpone its scan.
            minimum_scan_interval=0
            first_check="no"
        fi
        check_options "${minimum_scan_interval}"
        "${CHECK_EXECUTABLE}" "${CHECK_ARGUMENTS[@]}"
        status=$?
        if [ "${status}" -gt "${EXIT_FINDINGS}" ]; then
            consecutive_errors=$((consecutive_errors + 1))
            log "The check could not be performed (exit code ${status})." \
                "That is ${consecutive_errors} of the ${ERROR_TOLERANCE}" \
                "consecutive failures which are tolerated."
            if [ "${consecutive_errors}" -ge "${ERROR_TOLERANCE}" ]; then
                log "Giving up. The state of the configuration of this" \
                    "cluster is unknown, and an unknown state is reported as" \
                    "bad health rather than as a healthy service."
                exit "${EXIT_ERROR}"
            fi
            interruptible_sleep "${CHECK_INTERVAL_SECONDS}"
            continue
        fi
        consecutive_errors=0
        if [ "${report_link_checked}" = "no" ]; then
            check_report_link
            report_link_checked="yes"
        fi
        scan_exit_code=$(last_scan_exit_code)
        if [ -n "${scan_exit_code}" ] && [ "${RESULT_FILE}" -nt "${LOG_DIR:-/var/log/configuration-assurance}/coguard-report.md" ]; then
            write_report
        fi
        if [ "${scan_exit_code}" = "${EXIT_FINDINGS}" ]; then
            log "$(finding_summary)"
            log "Ending with a failure, so that Cloudera Manager reports this" \
                "service as unhealthy. Fix the configuration and restart this" \
                "role to check again. The findings are in the CoGuard report" \
                "above, and in full in the CoGuard Report this role links to."
            exit "${EXIT_FINDINGS}"
        fi
        if [ -z "${scan_exit_code}" ]; then
            log "No scan has been recorded yet. Waiting for one."
        fi
        interruptible_sleep "${CHECK_INTERVAL_SECONDS}"
    done
}

main() {
    local command=${1:-start}
    if [ "${command}" != "start" ]; then
        log "This script only knows how to start; it was asked to" \
            "\`${command}\`."
        exit "${EXIT_ERROR}"
    fi
    if ! read_configuration || ! read_credentials; then
        exit "${EXIT_ERROR}"
    fi
    if ! mkdir -p "${WORK_DIRECTORY}" 2> /dev/null \
       || [ ! -w "${WORK_DIRECTORY}" ]; then
        log "The working directory ${WORK_DIRECTORY} cannot be created or" \
            "written to by $(id -un)."
        exit "${EXIT_ERROR}"
    fi
    # The CLI writes its result into the current directory, so this is what puts
    # the result where the next check and the banner command can find it. The
    # process directory Cloudera Manager creates would not do: that is a new one
    # for every start of the role.
    cd "${WORK_DIRECTORY}" || exit "${EXIT_ERROR}"
    start
}

main "$@"

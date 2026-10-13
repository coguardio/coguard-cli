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
# Everything this needs is in the environment, put there by the startRunner of
# the descriptor, except the passwords: those are read from the credentials file
# named by ENVIRONMENT_FILE, so that they are not in the configuration database
# of Cloudera Manager, in its API or in its audit log.

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
    MINIMUM_FAIL_LEVEL=${MINIMUM_FAIL_LEVEL:-1}
    RULESET=${RULESET:-}
    CHECK_EXECUTABLE=${CHECK_EXECUTABLE:-coguard-cloudera-check}
    COGUARD_EXECUTABLE=${COGUARD_EXECUTABLE:-coguard}
    PYTHON_EXECUTABLE=${PYTHON_EXECUTABLE:-python3}
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
    if ! command -v "${CHECK_EXECUTABLE}" > /dev/null 2>&1; then
        log "The check command \`${CHECK_EXECUTABLE}\` was not found on the" \
            "PATH of $(id -un). Install the CoGuard CLI on this host with" \
            "\`pip3 install coguard-cli\`, or configure an absolute path."
        return 1
    fi
    return 0
}

read_credentials() {
    if [ -z "${ENVIRONMENT_FILE}" ]; then
        log "No credentials file is configured. The password of" \
            "${CLOUDERA_MANAGER_USER} has to come from the environment of" \
            "this process, which Cloudera Manager does not provide."
    elif [ ! -r "${ENVIRONMENT_FILE}" ]; then
        log "The credentials file ${ENVIRONMENT_FILE} does not exist or" \
            "cannot be read by $(id -un)."
        return 1
    else
        # Exported, because the check hands the password on to the scan through
        # the environment as well, and the CoGuard account is taken from
        # COGUARD_USER_NAME and COGUARD_PASSWORD when both are set -- as is
        # COGUARD_ORGANIZATION, which an account with several organizations
        # needs because there is nobody here to ask which one to scan into.
        set -a
        # shellcheck disable=SC1090
        . "${ENVIRONMENT_FILE}"
        set +a
    fi
    if [ -z "${CLOUDERA_MANAGER_PASSWORD:-}" ]; then
        log "CLOUDERA_MANAGER_PASSWORD is not set, so there is no way to" \
            "authenticate against Cloudera Manager. It belongs in the" \
            "credentials file, which is readable by $(id -un) and by nobody" \
            "else."
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
}

start() {
    local consecutive_errors=0
    local first_check="yes"
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
        scan_exit_code=$(last_scan_exit_code)
        if [ "${scan_exit_code}" = "${EXIT_FINDINGS}" ]; then
            log "$(finding_summary)"
            log "Ending with a failure, so that Cloudera Manager reports this" \
                "service as unhealthy. Fix the configuration and restart this" \
                "role to check again; the findings themselves are in the" \
                "report this role links to."
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

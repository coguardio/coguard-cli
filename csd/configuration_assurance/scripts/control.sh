#!/usr/bin/env bash
#
# The process Cloudera Manager supervises for the CoGuard Configuration Check
# role.
#
# The health signal of this service is whether this process is running: it
# stays alive while the scans of the cluster come back clean, and exits non-zero
# once one reports findings at or above the configured severity. Cloudera
# Manager reports that as a role whose process exited, which -- with the
# descriptor's healthAggregation -- turns the service red. (Cloudera Manager 7
# also reads metric health tests from a descriptor, which would allow a health
# test of our own; see ../README.md.)
#
# Two consequences of that mechanism, both of them also in ../README.md:
#
#   * While this service is red, nothing is scanning any more, because the
#     process which would scan is the one that exited. The badge does not go
#     green by itself once the configuration is fixed; restarting the role is
#     what re-checks. The first check after a start therefore ignores the
#     minimum scan interval -- a restart is somebody asking for a fresh look.
#   * The health is the outcome of the last scan, not of the last check: a check
#     with no scan due would exit 0. The check is therefore run with
#     --exit-with-last-scan, which makes its exit code the state of the
#     configuration as last scanned -- 0 clean, 1 findings, 2 no answer -- and
#     this script needs nothing else. The summary and the report of the
#     findings are printed by the check.
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
    # The commands of the COGUARD parcel. The variables are not parameters of
    # the service; they are only there to run this script against a stand-in
    # for the check, see "Working on it" in ../README.md.
    CHECK_EXECUTABLE=${CHECK_EXECUTABLE:-coguard-cloudera-check}
    COGUARD_EXECUTABLE=${COGUARD_EXECUTABLE:-coguard}
    WORK_DIRECTORY=${WORK_DIRECTORY:-/var/lib/coguard}
    CHECK_INTERVAL_SECONDS=${CHECK_INTERVAL_SECONDS:-900}
    MINIMUM_SCAN_INTERVAL_SECONDS=${MINIMUM_SCAN_INTERVAL_SECONDS:-900}
    MAXIMUM_SCAN_AGE_SECONDS=${MAXIMUM_SCAN_AGE_SECONDS:-86400}
    ERROR_TOLERANCE=${ERROR_TOLERANCE:-3}
    STATE_FILE="${WORK_DIRECTORY}/cloudera_check_state.json"
    REPORT_FILE="${LOG_DIR:-/var/log/configuration-assurance}/coguard-report.md"
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
    for executable in "${CHECK_EXECUTABLE}" "${COGUARD_EXECUTABLE}"; do
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

check_options() {
    local minimum_scan_interval=$1
    # --exit-with-last-scan makes the exit code the state of the configuration
    # as last scanned even when no scan is due, which is the one thing this
    # script needs to know; the check prints the summary and the report itself.
    CHECK_ARGUMENTS=(
        --exit-with-last-scan
        --report-file "${REPORT_FILE}"
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
    if [ -n "${COGUARD_ORGANIZATION:-}" ] && [ -n "${COGUARD_CLUSTER_NAME:-}" ]; then
        CHECK_ARGUMENTS+=(
            --coguard-cluster-name "${COGUARD_CLUSTER_NAME}"
            --report-url "${REPORT_URL:-https://portal.coguard.io}/orgs/${COGUARD_ORGANIZATION}/${COGUARD_CLUSTER_NAME}"
        )
    fi
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
    local minimum_scan_interval status
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
        if [ "${status}" -eq "${EXIT_FINDINGS}" ]; then
            log "Ending with a failure, so that Cloudera Manager reports this" \
                "service as unhealthy. Fix the configuration and restart this" \
                "role to check again. The findings are in the CoGuard report" \
                "above, and in full in the CoGuard Report this role links to."
            exit "${EXIT_FINDINGS}"
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

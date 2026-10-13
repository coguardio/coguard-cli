# `coguard_cli.cloudera_integration`

This package contains the commands which run the Cloudera scan on a schedule
and show its result in Cloudera Manager: they decide **when** a scan is worth
running, and put its result where the people who administer the cluster see
it. The scan itself is `coguard cloud cloudera`, implemented in
[`coguard_cli/discovery/cloudera_discovery`](../discovery/cloudera_discovery).

| File          | Contents                                                                    |
|---------------|-----------------------------------------------------------------------------|
| `__init__.py` | The connection options, credential resolution and exit codes shared by the entry points of this package. |
| `check.py`    | The `coguard-cloudera-check` entry point, i.e. one check per invocation.      |
| `banner.py`   | The `coguard-cloudera-banner` entry point, i.e. the result of a scan in the header of Cloudera Manager. |

The reference documentation of the integration as a whole — what is
collected, how roles become CoGuard cluster services, which files are
retrieved — is [`doc/integrations/cloudera.md`](../../../doc/integrations/cloudera.md).
This file is the usage documentation of the command in this folder.

## `coguard-cloudera-check`

```shell
export CLOUDERA_MANAGER_PASSWORD='<the password>'
coguard-cloudera-check \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user coguard
```

One invocation asks Cloudera Manager whether anything has changed the
configuration of the cluster, and runs `coguard cloud cloudera` if something
has. The scan it runs is the ordinary one, with the same rule sets, the same
output and the same portal results.

The configuration of a Cloudera cluster does not change on a schedule. It
changes when somebody changes it, and that is when a scan is worth running —
which is the whole reason this command exists rather than a cron line that
scans every hour regardless.

**When and how often the check runs is not this program's business.** A
systemd timer or a cron job already knows how to catch up after downtime,
spread a fleet out over an interval, restart on failure and log where an
operator looks. There is no `--interval`, and no daemon.

## What counts as a change

The check reads Cloudera Manager's event feed, one query per watched event
code:

```
GET /api/{version}/events?query=attributes.EVENTCODE==EV_REVISION_CREATED&maxResults=50
```

An `EV_REVISION_CREATED` event *is* a configuration change, and names the
parameter, its new value, the user, the service and the role config group:

```
content:    "User admin created a new revision. Message was: Setting the
             value of ozone_security_enabled to true."
attributes: REVISION, USER, CLUSTER, SERVICE, SERVICE_TYPE, ROLE,
            ROLE_CONFIG_GROUP, HOSTS, EVENTCODE, URL
```

A revision which names **no** cluster is a change to the configuration of
Cloudera Manager *itself* — its banner, its header colour, the address it sends
alerts from — and is ignored, because it cannot change the generated
configuration files of any role. That is also what keeps the integration from
chasing its own tail: `coguard-cloudera-banner` writes into that configuration,
which produces such a revision, which would otherwise be read as a change at the
next check, which would scan, which would write the banner again. Filtering by
the parameter which changed is not an option, by the way — the `content` of those
events is `User admin created a new revision. Message was: null.`

The codes in `WATCHED_EVENT_CODES` are that event plus the moments at which a
change takes effect or the topology changes: the restart codes, the start and
stop codes of services and roles, the creation and deletion of services and
roles, `EV_HOST_TEMPLATE_APPLIED`, and `EV_PARCEL_ACTIVATE` for a new software
version. All of them were observed on Cloudera Manager 7.13; the starts and
restarts of the Cloudera Management Service, which
belongs to no cluster, are ignored. `--event-code` replaces the
list, so a cluster which reports a change through another code can be
followed without a new release; a code Cloudera Manager does not know simply
matches nothing.

`GET /audits` is deliberately *not* used. It records **operations** —
logins, commands, the creation of services, roles and host templates — and
not the values of configuration parameters. Across 563 audit entries of a
live cluster, covering its entire deployment and 100 distinct operation
kinds, not one was a configuration parameter change. There is also no
configuration revision resource to ask instead: `.../config/revisions` and
`/cm/config/revisions` answer `404` on API v58.

### Why there is a state file

Because the events resource has no server-side time filter. `timeOccurred`
is not a queryable attribute (`400 Missing comparator in comparison
expression`), and `from` and `to` parameters are accepted and then ignored.
The caller therefore has to remember where it stopped, and that is all the
state file is: the timestamp of the newest event seen, plus what the last
scan did.

```json
{
  "cluster": "ozone-base-cluster",
  "lastEventAt": "2026-09-04T16:31:15.041Z",
  "lastCheckedAt": "2026-09-06T03:26:56+00:00",
  "lastScanAt": "2026-09-06T03:26:57+00:00",
  "lastScanReason": "ozone: User admin created a new revision. Message was: ...",
  "lastScanExitCode": 0
}
```

The watermark is advanced only when a scan has actually run, so a change
which was postponed, or whose scan could not be started, is still a change at
the next check. A state file which is missing, unreadable or about another
cluster leads to a scan and a new watermark, i.e. the failure direction is
"scan too often", never "miss a change".

## Options

The connection options are the ones of `coguard cloud cloudera`
(`--cloudera-manager-url`, `--cloudera-manager-user`,
`--cloudera-manager-ca-cert`, `--cloudera-cluster`, `--credentials-file`). As there, the password is **not**
a command line option, so that it stays out of the shell history and the
process list: it comes from `CLOUDERA_MANAGER_PASSWORD`, from the
credentials file, or from an interactive prompt. It is handed to the scan
through its environment, never on its command line.

| Option                    | Default                                            | Description                                                                 |
|---------------------------|----------------------------------------------------|-----------------------------------------------------------------------------|
| `--event-code`            | `WATCHED_EVENT_CODES`                              | An event code to treat as a configuration change. May be repeated, and replaces the default set. |
| `--minimum-scan-interval` | `900`                                              | Lower bound on the distance between two scans.                               |
| `--maximum-scan-age`      | `86400`                                            | Scan after this many seconds even if no event reported a change.             |
| `--state-file`            | `~/.config/coguard-cli/cloudera_check_state.json`  | Where the watermark and the outcome of the last scan are kept.               |
| `--coguard-cli`           | `coguard`                                          | The executable to perform the scan with.                                     |
| `--minimum-fail-level`    | the CLI's own default of `1`                       | Passed through to `coguard`.                                                 |
| `--ruleset`               | —                                                  | Passed through to `coguard`, e.g. `nist800-53`.                              |
| `--coguard-api-url`, `--coguard-auth-url` | —                                  | Passed through to `coguard`.                                                 |

`--minimum-scan-interval` exists because a rolling restart produces one event
after another, and a scan takes minutes; without a lower bound, a restart of
the cluster would result in a scan per service.

`--maximum-scan-age` is what makes this safe to rely on. The event feed is a
change *hint*, not a guarantee: events are retained for a finite time
(`AUDIT_RECORDS_LIFE_TIME`, 720 hours by default), the feed is served by the
Event Server role and is unavailable while that role is down, and CoGuard
adds rules over time. The periodic scan bounds how long the report can be out
of date.

## Exit codes

| Exit code | Meaning                                                                                       |
|-----------|-----------------------------------------------------------------------------------------------|
| `0`       | No scan was due, or the scan ran and found nothing at or above the fail level.                  |
| `1`       | The scan ran and found something at or above the fail level.                                   |
| `2`       | The check itself failed: Cloudera Manager could not be read, or `coguard` could not be run.     |

`0` and `1` come from `coguard` itself when a scan ran, so the check behaves
in a pipeline exactly like a manual scan. A scan which fails *inside* the CLI
also exits `1` and is therefore not distinguishable from findings by the exit
code alone; its output says which of the two happened. `2` is reserved for
the failures the check detects itself, and in that case nothing is recorded
as scanned, so the next check retries.

## `coguard-cloudera-banner`

```shell
export CLOUDERA_MANAGER_PASSWORD='<the password>'
coguard --output-format json cloud cloudera \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user coguard
coguard-cloudera-banner \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user coguard-admin \
    --report-url https://portal.coguard.io/dashboard
```

This reads the `result.json` a scan wrote and puts a summary of it into the
header of Cloudera Manager.

The point is that the people who administer the cluster see the state of its
configuration in the place where they administer it, rather than only in a
portal they have to remember to open. A clean result is shown too, because "no
findings" and "no scan ran" are worth telling apart.

The parameter written is `CUSTOM_BANNER_HTML` of the Cloudera Manager service
configuration, which Cloudera provides for exactly this purpose. Three things
follow from what that parameter actually is:

* **What goes in is plain text, in spite of the name.** Cloudera Manager 7.13
  escapes the value and shows it verbatim, so markup put in it is shown as
  markup; Cloudera's own validation calls it "the Custom Banner Text parameter".
  Plain text is also the only form which survives both behaviours. There is
  therefore no colour to signal with, so the line says whether there are
  findings before it says anything else, and the address of the report is written
  out rather than linked. Values taken from the result have `<` and `>` removed,
  so that a service name cannot become markup on a version which renders the
  value.
* **The banner is shared.** A customer may already display something in it, and
  that text is not ours to remove. The region written here runs from `CoGuard:`
  to the end of the value, i.e. this command writes last and keeps what is in
  front of it. Running the command twice leaves one summary, not two, and
  `--clear` removes the region and the separator in front of it and nothing else.
  A banner left by the earlier version of this command, which used
  `<!--coguard:start-->` and `<!--coguard:end-->`, is recognised and replaced.
* **It stays short.** It is a header, not a report. Only the counts and the
  worst affected services are named, capped by `--max-services`, with the detail
  left to the report the banner points to.

### The colour is one level up

The colour the banner text cannot have is available on the header bar the banner
sits in. `CUSTOM_HEADER_COLOR` is what Cloudera Manager tints that bar with, and
`--header-color` makes it follow the scan:

```shell
coguard-cloudera-banner \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user coguard-admin \
    --header-color RED
```

Red while there are findings, back to `--header-color-clean` once there are none.
That is the difference between a line of text somebody may read and a page nobody
can open without noticing.

It is off by default, and it puts the colour back only while the header still has
the colour it set, because Cloudera provides that parameter to "distinguish
different instances of Cloudera Manager" and a customer may be using it for
exactly that. An instance which is normally recognised by its colour should name
that colour as `--header-color-clean`.

The accepted values are `BLACK`, `GRAY`, `RED`, `YELLOW`, `GREEN`, `TEAL`,
`BLUE`, `PURPLE`, `PINK` and `BROWN`. The API does not publish them — not one of
the 282 parameters of the resource comes with `validValues` — and neither does
the documentation, so they were read off the assets the header is built from:
Cloudera Manager ships one `favicon-<COLOUR>.png` per value.

Both parameters go into a single request, because one request is one configuration
revision, and writing them separately would appear in the event feed and in the
audit trail as two changes where an operator made none.

| Option                | Default        | Description                                                                        |
|-----------------------|----------------|------------------------------------------------------------------------------------|
| `--result-file`       | `result.json`  | The result JSON of the scan, as written by `coguard --output-format json`.           |
| `--minimum-severity`  | `1`            | Only count findings at or above this severity, i.e. all of them by default.          |
| `--max-services`      | `5`            | How many affected services to name before summarizing the rest as a count.           |
| `--report-url`        | —              | What the "Full report" link points at, e.g. the cluster in the CoGuard portal.        |
| `--header-color`      | off            | Colour the header bar in this colour while there are findings. The header is not touched at all without it. |
| `--header-color-clean`| `BLACK`        | What the header goes back to once there are none. Cloudera Manager's own default.     |
| `--clear`             | off            | Remove the CoGuard region from the banner, and put the header colour back. No scan result is read. |
| `--dry-run`           | off            | Print the banner which would be written, and write nothing.                          |

The connection options are the same ones as above. **This is the one command of
the integration which changes the cluster**, and writing the Cloudera Manager
service configuration requires the Full Administrator role, unlike the read-only
scan. It is therefore meant to be given a credential of its own — the example
above uses `coguard-admin` for the banner and `coguard` for the scan — so that
the account which scans continuously keeps the least privilege it needs.

Nothing is written when the banner already says the same thing, so a scheduled
run does not produce a configuration revision per invocation. Since the scan
timestamp is part of the text, that applies in practice to `--clear` against an
already empty banner; a new scan result always differs.

## Scheduling it

A oneshot service and a timer. The state file is pointed at
`StateDirectory=`, so that it survives and is not looked for in a home
directory the unit cannot see. `ProtectHome=true` works because the CoGuard
account is taken from `COGUARD_USER_NAME` and `COGUARD_PASSWORD`. The
environment and `~/.config/coguard-cli/coguard_conf` are an either-or: with
both variables set the file is not read at all, including the CoGuard URLs a
login stored in it, so pass `--coguard-api-url` and `--coguard-auth-url` for a
CoGuard other than `portal.coguard.io`; with only one of them set, the
variable is ignored and the file is used alone, in which case `ProtectHome`
has to go. An account with several CoGuard organizations needs
`COGUARD_ORGANIZATION` as well: interactively the CLI asks which organization
a scan belongs to, and a unit has nobody to ask.

```ini
# /etc/systemd/system/coguard-cloudera-check.service
[Unit]
Description=CoGuard configuration scan of the Cloudera cluster
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=coguard
# 0600, owned by root, holding CLOUDERA_MANAGER_PASSWORD and the CoGuard
# account as COGUARD_USER_NAME and COGUARD_PASSWORD.
EnvironmentFile=/etc/coguard/cloudera.env
# Only needed if the CoGuard account has more than one organization.
Environment=COGUARD_ORGANIZATION=example
StateDirectory=coguard
ExecStart=/usr/local/bin/coguard-cloudera-check \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user coguard \
    --state-file /var/lib/coguard/cloudera_check_state.json
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
```

```ini
# /etc/systemd/system/coguard-cloudera-check.timer
[Unit]
Description=Check the Cloudera cluster configuration regularly

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
# Run a missed check after downtime instead of waiting for the next slot.
Persistent=true
# Keep a fleet of clusters from checking in at the same second.
RandomizedDelaySec=2min

[Install]
WantedBy=timers.target
```

For cron, the equivalent is a single line, with the caveats that the
environment is not the one of a login shell and that a missed run is simply
missed:

```cron
*/15 * * * * . /etc/coguard/cloudera.env && /usr/local/bin/coguard-cloudera-check --cloudera-manager-url https://cm.example.com --cloudera-manager-user coguard --state-file /var/lib/coguard/cloudera_check_state.json
```

### Updating the banner along with it

The banner reads the result file the scan wrote, and `coguard` writes
`result.json` into its working directory, so the two have to agree on one.
`WorkingDirectory=` in the unit above is the place to say it, and the banner is
then an `ExecStartPost=`, which runs whether the check found something or not:

```ini
WorkingDirectory=/var/lib/coguard
# `-` so that a banner which cannot be written does not turn a completed scan
# into a failed unit.
ExecStartPost=-/usr/local/bin/coguard-cloudera-banner \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user coguard-admin \
    --result-file /var/lib/coguard/result.json \
    --report-url https://portal.coguard.io/dashboard \
    --header-color RED
```

The banner needs its own, more privileged credential, which
`CLOUDERA_MANAGER_PASSWORD` in a shared `EnvironmentFile=` cannot express. Give
the banner a `--credentials-file` of its own, or run it from a second unit whose
`EnvironmentFile=` holds the administrator password.

### Or as a Cloudera service

[`csd/configuration_assurance`](../../../csd) is a custom service descriptor which
runs `coguard-cloudera-check` as a role of a Cloudera service instead, so that
Cloudera Manager is both the scheduler and the place the result is shown: the role
stays up while the checks come back clean and exits non-zero when a scan reports
findings, which is what Cloudera Manager renders as a red badge on the service and
as bad cluster health. It is a jar in `/opt/cloudera/csd` and a restart of the
Cloudera Manager server, and the parameters of the service are the options above.
[`csd/README.md`](../../../csd/README.md) has the installation and the limits of
that mechanism — chiefly that a CSD cannot declare a health test of its own, so the
badge lands on that service rather than on the service a finding belongs to.

## Working on this package

```shell
make unit-test   # pytest with coverage, and the README parity check
make lint        # pylint against .pylint.rc
```

The tests are in
[`coguard_cli/tests/cloudera_integration`](../tests/cloudera_integration).
`check_test.py` builds Cloudera Manager answers out of the `event()` helper
and never touches a network; `api_with()` answers the event queries from a
mapping of event code to events. `banner_test.py` does the same for the
configuration resource, out of `finding()` and `result_file()`. All three
modules of this package are covered completely, and are expected to stay that
way.

The client this package calls is `ClouderaManagerApi`. It issues `GET`
requests only and must not modify a cluster; its urls are assembled field by
field with per-segment and per-parameter validation rather than by string
concatenation. The one exception is `ClouderaManagerBannerApi` in `banner.py`,
which adds the single `PUT` that writes the banner and is used by nothing else.
A new request which modifies the cluster belongs in a subclass of its own for
the same reason, not in the client the scan uses.

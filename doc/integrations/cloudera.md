# CoGuard Cloudera integration

## Overview

CoGuard integrates with [Cloudera
Manager](https://docs.cloudera.com/cloudera-manager/7.13.1/index.html),
the management layer of a Cloudera Private Cloud Base deployment, to scan
the configurations of a running cluster.

The essential property of this integration is that CoGuard retrieves the
**generated** configuration files of each process, i.e. the files as they
were actually written to the hosts by Cloudera Manager. The effective
configuration is not reconstructed from the service configuration JSON,
and therefore inherited defaults, role config group overrides and safety
valve additions are all taken into account exactly as deployed.

Cloudera's own domain model maps almost directly onto CoGuard's cluster
representation:

| Cloudera Manager | CoGuard                                |
|------------------|----------------------------------------|
| cluster          | cluster                                |
| service          | service name (the applicable rule set)  |
| role             | cluster service (the scanned instance)  |
| generated config | configuration file                     |

## Prerequisites

- A Cloudera Manager instance reachable from the machine running the CLI.
- A Cloudera Manager user with read access to the cluster.
- A CoGuard account.
- Only for `coguard-cloudera-banner`: a second Cloudera Manager user with the
  Full Administrator role, which is what writing the header banner requires.

## Usage

```shell
export CLOUDERA_MANAGER_PASSWORD='<the password>'
coguard cloud cloudera \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user admin
```

### Options

| Option                           | Environment variable        | Description                                                                            |
|----------------------------------|-----------------------------|----------------------------------------------------------------------------------------|
| --cloudera-manager-url           | CLOUDERA_MANAGER_URL        | The URL of Cloudera Manager. A bare host name is accepted and assumed to be `https`.    |
| --cloudera-manager-user          | CLOUDERA_MANAGER_USER       | The Cloudera Manager user to authenticate as.                                           |
| N/A                              | CLOUDERA_MANAGER_PASSWORD   | The password. Prompted for interactively if the variable is unset and a terminal exists. |
| --cloudera-manager-ca-cert       | CLOUDERA_MANAGER_CA_CERT    | A CA certificate bundle to trust for the TLS connection.                                 |
| --cloudera-manager-no-verify-tls | CLOUDERA_MANAGER_VERIFY_TLS | Skip TLS verification, e.g. for a self-signed certificate behind a reverse proxy.        |
| --cloudera-cluster               | CLOUDERA_CLUSTER            | The cluster to scan. Only needed if Cloudera Manager manages more than one cluster.     |

The values can also be placed into a JSON or YAML file, passed via
`--credentials-file`, using the keys `url`, `username`, `password`,
`ca_cert`, `verify_tls` and `cluster`:

```yaml
url: https://cm.example.com
username: admin
password: the-password
cluster: my-cluster
```

Command line options take precedence over the credentials file, which in
turn takes precedence over the environment variables.

The password is deliberately not available as a command line option, so
that it does not end up in the shell history or the process list.

## Scheduled scanning

A cluster is not scanned once. `coguard-cloudera-check`, installed along
with the CLI, performs one check per invocation: it asks Cloudera Manager
whether the configuration of the cluster has changed, and runs `coguard
cloud cloudera` if it has.

```shell
export CLOUDERA_MANAGER_PASSWORD='<the password>'
coguard-cloudera-check \
    --cloudera-manager-url https://cm.example.com \
    --cloudera-manager-user coguard
```

The same description lives next to the code, in
[`src/coguard_cli/cloudera_integration/README.md`](../../src/coguard_cli/cloudera_integration/README.md).

It accepts the connection options listed above, including
`--credentials-file`, and does not take a password on the command line. The
scan it runs is the ordinary one, with the same rule sets, the same output
and the same portal results — the only thing added is the decision whether
to run it at all.

**When** and **how often** the check runs is deliberately not this
program's business. A systemd timer or a cron job already knows how to
catch up after downtime, spread a fleet out over an interval, restart on
failure and log where an operator looks, and re-implementing that inside a
scanner would be worse at all four. What cannot be moved out to a
scheduler is how far the event feed of Cloudera Manager has already been
read, which is what the state file holds.

### What counts as a change

The check asks Cloudera Manager's event feed what has happened:

```shell
GET /api/{version}/events?query=attributes.EVENTCODE==EV_REVISION_CREATED
```

An `EV_REVISION_CREATED` event *is* the configuration change, and says which
parameter was set to what, by whom, in which service and role config group:

```json
{
  "content": "User admin created a new revision. Message was: Setting the value of ozone_security_enabled to true.",
  "timeOccurred": "2026-09-04T16:20:37.738Z",
  "attributes": [
    {"name": "EVENTCODE", "values": ["EV_REVISION_CREATED"]},
    {"name": "USER", "values": ["admin"]},
    {"name": "SERVICE", "values": ["ozone"]},
    {"name": "ROLE_CONFIG_GROUP", "values": ["ozone-OZONE_MANAGER-BASE"]},
    {"name": "REVISION", "values": ["1546338003"]}
  ]
}
```

One query is issued per watched event code:

| Event code                                                     | What it means for the configuration                  |
|----------------------------------------------------------------|------------------------------------------------------|
| `EV_REVISION_CREATED`                                          | A configuration parameter was set to a new value.     |
| `EV_CLUSTER_RESTARTED`, `EV_SERVICE_RESTARTED`, `EV_ROLE_RESTARTED` | A change reached the running processes, i.e. the generated configuration files are now the ones in force. |
| `EV_SERVICE_CREATED`, `EV_SERVICE_DELETED`, `EV_ROLE_CREATED`, `EV_ROLE_DELETED`, `EV_HOST_TEMPLATE_APPLIED` | The cluster has a service or role it did not have before, or lost one. |
| `EV_PARCEL_ACTIVATE`                                           | A new software version, whose generated configuration files are new as well. |

`--event-code` replaces that list, so a Cloudera Manager which reports a
change through a code not named here can be followed without a new release.
A code Cloudera Manager does not know is not an error — the query simply
matches nothing.

The audit feed, `GET /audits`, is deliberately *not* what is asked. It
records **operations** — logins, commands, the creation of services, roles
and host templates — and not the values of configuration parameters. Across
563 audit entries of a live cluster, spanning its entire deployment and 100
distinct operation kinds, not one described a configuration parameter
change. The per-service audit and configuration revision resources
(`.../config/revisions`, `/cm/config/revisions`) answer `404` on API v58,
i.e. Cloudera Manager's "History and Rollback" view is not exposed.

| Option                    | Default | Description                                                                       |
|---------------------------|---------|-----------------------------------------------------------------------------------|
| `--event-code`            | see above | An event code to treat as a configuration change. May be repeated, and replaces the default set. |
| `--minimum-scan-interval` | 900     | Lower bound on the distance between two scans.                                     |
| `--maximum-scan-age`      | 86400   | Scan after this many seconds even if no event reported a change.                    |
| `--state-file`            | `~/.config/coguard-cli/cloudera_check_state.json` | Where the position in the event feed and the outcome of the last scan are kept. |

The state file is needed because the events resource has **no server-side
time filter**: `timeOccurred` is not a queryable attribute (`400 Missing
comparator`), and `from` and `to` parameters are accepted and ignored. The
check therefore remembers the timestamp of the newest event it has seen and
treats everything newer than that as new. That watermark is the whole of the
state; a check whose state file is missing scans and starts a new one.

`--minimum-scan-interval` exists because a rolling restart produces one
event after another. Without a lower bound, such a restart would result in a
scan per service; a change which is postponed by it stays a change, because
the watermark is only advanced once a scan has actually run.

`--maximum-scan-age` is what makes this safe to rely on. The event feed is a
change *hint*, not a guarantee: events are retained for a finite time
(`AUDIT_RECORDS_LIFE_TIME`, 720 hours by default), the feed is served by the
Event Server role and is unavailable while that role is down, and CoGuard
adds rules over time. The periodic scan bounds how long the report can be
out of date, and is also what picks up findings from new rules.

### Exit codes

| Exit code | Meaning                                                                        |
|-----------|--------------------------------------------------------------------------------|
| 0         | No scan was due, or the scan ran and found nothing at or above the fail level.   |
| 1         | The scan ran and found something at or above the fail level.                     |
| 2         | The check itself failed: Cloudera Manager could not be read, or `coguard` could not be run. |

`0` and `1` come from `coguard` itself when a scan ran, so the check behaves
in a pipeline exactly like a manual scan does. `--minimum-fail-level` is
passed through unchanged; the CLI's default of `1` — any finding fails —
applies unless it is given.

Note that a scan which fails *inside* the CLI, e.g. because the CoGuard API
was unreachable, also exits `1` and is therefore not distinguishable from
findings by the exit code alone. Its output says which of the two happened.
Exit code `2` is reserved for the failures the check detects itself, and in
that case nothing is recorded as scanned, so the next check retries.

### As a systemd timer

A oneshot service, triggered by a timer:

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

```shell
systemctl enable --now coguard-cloudera-check.timer
```

Two notes on the unit:

- The CoGuard account is taken from `COGUARD_USER_NAME` and
  `COGUARD_PASSWORD` when both are set, which is why `ProtectHome=true`
  works here. Without them the CLI reads
  `~/.config/coguard-cli/coguard_conf`, which it writes on the first
  login — in that case drop `ProtectHome`, and keep the state file in the
  home directory as well.
- `--state-file` is pointed at `StateDirectory=`, i.e. `/var/lib/coguard`,
  so that the state survives and is not looked for in a home directory the
  unit cannot see.

For cron instead of systemd, the equivalent is a single line, with the
caveats that the environment is not the one from a login shell and that a
missed run is simply missed:

```cron
*/15 * * * * . /etc/coguard/cloudera.env && /usr/local/bin/coguard-cloudera-check --cloudera-manager-url https://cm.example.com --cloudera-manager-user coguard --state-file /var/lib/coguard/cloudera_check_state.json
```

## Showing the result in Cloudera Manager

A report which has to be looked for is a report which is not looked at. The
command `coguard-cloudera-banner`, installed along with the CLI, takes the
`result.json` of a scan and puts a summary of it into the header of Cloudera
Manager, where the people who administer the cluster already are:

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

> **CoGuard: 89 configuration findings of ozone-base-cluster (44 High, 35
> Medium, 10 Low), affecting ozone_datanode (11), ozone_manager (11),
> ozone_recon (11), ozone_s3_gateway (11),
> ozone_storage_container_manager (11) and 12 further services. Scanned
> 2026-09-08 18:57 UTC.** [Full report](https://portal.coguard.io/dashboard).

The parameter written is `CUSTOM_BANNER_HTML` of the Cloudera Manager service
configuration, which Cloudera provides for exactly this purpose. Only the
region between `<!--coguard:start-->` and `<!--coguard:end-->` is written, so a
banner which is already in use is preserved and running the command twice
leaves one summary rather than two; `--clear` removes the region again.
Everything taken from the scan result is HTML-escaped, since the banner is
rendered as raw HTML on every page.

**This is the one command of the integration which changes the cluster.**
Writing the Cloudera Manager service configuration requires the Full
Administrator role, unlike the read-only scan, so it is meant to be given a
credential of its own rather than the one the scan uses. The full option list,
and how to attach it to the timer above, are in
[`src/coguard_cli/cloudera_integration/README.md`](../../src/coguard_cli/cloudera_integration/README.md).

## Gating a change in a pipeline

Cloudera Manager offers nothing that can block a configuration change before
it takes effect, so a gate cannot sit inside it; it sits in the pipeline which
produces the change. What makes that a gate is the exit code of a scan: a
finding at or above `--minimum-fail-level` exits `1` and fails the job.

```shell
coguard pipeline github add <PATH_TO_YOUR_REPOSITORY> --cloud cloudera
```

This writes `.github/workflows/coguard_cloudera_gate.yml`, next to — not
instead of — the `coguard_scan.yml` that `coguard pipeline github add` writes
for the repository itself. The two scan different things: that one reads the
infrastructure-as-code in the repository, this one reads the cluster.

The workflow is callable, which is how the job that changes the cluster gates
itself:

```yaml
jobs:
  apply:
    steps: [ ... whatever changes the cluster ... ]
  gate:
    needs: apply
    uses: ./.github/workflows/coguard_cloudera_gate.yml
    secrets: inherit
```

Gating *after* the change rather than before it is deliberate. What a rule is
evaluated against is the generated configuration of a running role, and that
only exists once Cloudera Manager has generated it. A pipeline which needs to
avoid the window in which a bad configuration is live can apply the change to
a staging cluster, gate on that, and promote on a green run — which is the
same shape as gating a schema migration.

Three things about the generated workflow are worth knowing.

**It needs to reach Cloudera Manager.** A GitHub hosted runner usually
cannot reach an on-premise cluster, so `runs-on` is the first thing to
change; a self-hosted runner on a host which can reach Cloudera Manager is
what belongs there. Nothing about the scan requires the runner to be inside
the cluster, only to be able to make HTTPS requests to Cloudera Manager.

**It uses two accounts, and one of them is read-only.** `COGUARD_USER_NAME`
and `COGUARD_PASSWORD` are the CoGuard account; `CLOUDERA_MANAGER_USER` and
`CLOUDERA_MANAGER_PASSWORD` are a Cloudera Manager user with no more than a
read-only role, since scanning only ever reads. All four are handed to the
CLI through the environment rather than the command line, so that they stay
out of the process list of the runner. The banner account, which does need
Full Administrator, has no business in a gate and is not part of this
workflow.

**The fail level is what makes it adoptable.** A cluster which has been
running for a while has findings, so a gate at `--minimum-fail-level 1` is
red on the first day, and a gate which is red on the first day gets switched
off. The generated workflow therefore fails on severity 4 and above and
publishes the whole result as GitHub code scanning alerts, where the findings
below that level are visible, tracked and dismissible without failing
anything. Lower the level as they get addressed.

The alerts are the `--output-format sarif` result of the scan. Their file
paths are the paths inside the cluster, e.g.
`ozone-conf/ozone-site.xml`, and do not correspond to files in the
repository, so they show up without a source snippet. Two services which
were both scanned and both have a finding in a file of the same name share
one alert.

## How it works

For the chosen cluster, the CLI walks the following endpoints of the
Cloudera Manager REST API.

1. `GET /api/{version}/clusters` — to determine the cluster. If Cloudera
   Manager manages exactly one cluster, it is selected automatically.
2. `GET /clusters/{cluster}/services` — the deployed services, e.g.
   `KAFKA`, `HDFS`, `RANGER`, `OZONE`.
3. `GET /clusters/{cluster}/services/{service}/roles` — the roles of each
   service, e.g. `KAFKA_BROKER`, `NAMENODE`, `RANGER_ADMIN`.
4. `GET .../roles/{role}/process` — the process of a role, which lists the
   generated configuration files available for it.
5. `GET .../roles/{role}/process/configFiles/{configFileName}` — the
   content of each of those files.

The API version is negotiated via `GET /api/version`, so that both older
and newer Cloudera Manager releases are supported.

`coguard-cloudera-check` adds one more endpoint, `GET /events`, which it
reads to decide whether a scan is due. Every request of the scan and of the
check is a `GET`; neither modifies anything in the cluster. The one request of
this integration which is not a `GET` is the `PUT /cm/config` of
`coguard-cloudera-banner`, and it is only made when that command is run.

### From roles to CoGuard cluster services

One CoGuard cluster service is created per *(service, role type)* pair,
rather than per role instance. A cluster with three Kafka brokers has one
`kafka_broker` entry, since the configuration of the brokers within a
role config group is identical, and a finding on one broker applies to
the group. Where a role type is present multiple times, a role in state
`STARTED` is preferred as the representative, so that the configuration
of a running process is scanned.

The resulting identifier drops a redundant service prefix, giving names
such as `kafka_broker`, `hdfs_namenode`, `ozone_recon` and `knox`.

The `serviceName` — the CoGuard rule set that applies — is derived from the
Cloudera service **type**, not from the service name and not from the names
of the generated configuration files:

- The service *name* is chosen freely by whoever created the service. The
  same Kafka service can be called `kafka`, `messaging` or `prod-1`, so it
  says nothing about the software it runs.
- The service *type* is fixed by the service descriptor Cloudera ships. Kafka
  is `KAFKA` in every Cloudera Manager instance, because the type is what
  Cloudera Manager uses to decide which roles, configuration parameters and
  generated files a service has to begin with.
- The generated *file names* cannot serve as the signal either, because roles
  legitimately ship the configuration of the services they talk to. A Kafka
  broker is handed an `atlas-application.properties`, and YARN and Spark
  roles receive `hive-site.xml` and `hdfs-site.xml`.

Most types already name their software and are simply lower-cased: `KAFKA` →
`kafka`, `OZONE` → `ozone`, `RANGER_KMS` → `ranger_kms`. The exceptions are the
types under which Cloudera packages software of a different name, and those are
translated:

| Cloudera service type | CoGuard service name |
|-----------------------|----------------------|
| `HIVE_ON_TEZ`         | `hive`               |
| `HIVE_LLAP`           | `hive`               |
| `SPARK_ON_YARN`, `SPARK2_ON_YARN`, `SPARK3_ON_YARN`, … | `spark` |
| `LIVY_FOR_SPARK3`, …  | `livy`               |
| `SQOOP_CLIENT`        | `sqoop`              |

This table is a translation of a vocabulary Cloudera controls, not a guess about
a particular cluster. The type of a service is fixed by the service descriptor,
and Cloudera Manager enumerates the types it has a descriptor for:

```shell
GET /api/{version}/clusters/{cluster}/serviceTypes
```

The CLI queries that endpoint on every scan and reports the declared types it has
no knowledge of, so that a type introduced by a later Cloudera release or by a
third-party service descriptor becomes a visible message rather than a silent
assumption:

```
Cloudera Manager offers service types which this version of CoGuard has not
been told about: SOMETHING_NEW. Services of these types are reported under
their Cloudera type name.
```

A type the table does not list is additionally read for the structure Cloudera
composes its type names with, since `SPARK4_ON_YARN` and `HIVE_ON_FLINK` are
going to exist before this table has heard of them:

- the major version of the packaged software, as in `SPARK3_ON_YARN`;
- the `X_ON_Y` and `X_FOR_Y` form, i.e. "software `X`, running on engine `Y`".

Both are used to *look a service name up*, never to construct one. The result has
to be either an entry of the table or a Cloudera service type in its own right,
which is what keeps the reading from producing something nobody described:

| type | result | why |
|------|--------|-----|
| `SPARK5_ON_KUBERNETES` | `spark` | the table names `SPARK_ON_YARN` as spark |
| `HIVE_ON_FLINK`        | `hive`  | `HIVE` is a Cloudera service type |
| `LIVY_FOR_SPARK4`      | `livy`  | the table names `LIVY_FOR_SPARK3` as livy |
| `WIDGET_ON_YARN`       | `widget_on_yarn` | nothing establishes a `widget` |

The [service descriptor
reference](https://github.com/cloudera/cm_ext/wiki/Service-Descriptor-Language-Reference)
does not specify this structure — it requires a type only to be globally unique,
upper-case and made of letters, digits and underscores — so it is a reading of
how Cloudera names things rather than a contract Cloudera has to honour, and a
descriptor from another vendor may well use the same shape for something else.
Restricting the outcome to service names that are already established is what
bounds the consequence: the reading can be useless for such a type, but it
cannot rename it to something invented. Such a type keeps its own name and is
reported by the coverage check above.

Nothing in the API states the underlying software directly, which was checked
against a live cluster on API v58:

- A service in the full view carries only its type, an operator-chosen display
  name, and a platform version (`CDH 7.3.2`).
- A role's process resource lists its configuration files, not the program it
  runs.
- The human-readable service `label` of the descriptor (`Hive on Tez`) is not
  exposed by the API; `GET /cm/csds` answers `404`, and `serviceTypes` returns
  plain identifiers even in the full view.
- The `relatedName` of a configuration parameter, which names the
  corresponding property of the underlying software, is set on a minority of
  parameters (61 of 280 for Kafka) and is dominated by the service's
  dependencies. The most frequent one for Kafka is `log`, followed by `oauth`,
  `atlas` and `ranger`.

Services for which CoGuard has no rule set yet are still part of the cluster
representation, so adding a rule set later requires no change to the CLI.

### Which files are collected

A process lists more than configuration: control scripts, Jinja
templates, keystores, keytabs and CSV mappings are among the entries.
Only files which CoGuard can parse are collected, and their CoGuard
configuration file type is derived from the name:

- `.properties`, `.cfg` → `properties`
- `.xml` → `xml`
- `.json` → `json`
- `.yaml`, `.yml` → `yaml`
- `.ini` → `ini`, `.toml` → `toml`
- `krb5.conf` → `krb`
- other `.conf` → `custom`

Scripts (`.sh`, `.py`), templates (`.j2`), key material (`.jks`, `.jceks`,
`.keytab`, `.pem`, ...), archives and the contents of the `scripts/` and
`aux/templates/` directories are skipped. Multi-level file names such as
`hadoop-conf/hdfs-site.xml` are preserved as a sub-path, so that the
directory layout of the deployed configuration is retained.

Roles which have never been started have no process, and are logged and
skipped; the same holds for services without roles, such as
`CORE_SETTINGS`.

One more class of file is skipped, and the criterion is worth spelling out
because the obvious version of it is wrong. Cloudera leaves unresolved
placeholders in files it has genuinely deployed: `{{CMF_CONF_DIR}}` appears
inside the *values* of `hdfs-site.xml`, `ozone-site.xml`, `kafka.properties`
and 145 other files of one live cluster, and the agent expands it when it
starts the process. Those files are exactly what this integration is for, so
a placeholder is not by itself a reason to skip anything.

What is skipped is a file whose placeholder sits in a structural position and
takes the syntax of the file with it — the Prometheus files of the Ozone
roles, whose `scrape_interval: {{SCRAPE_INTERVAL}}` is not YAML, and the
shared providers and descriptors of Knox, whose bare `PROXYUSER_BLOCK,` is not
JSON. Those are the input of a templating step rather than a configuration any
process reads, and no rule can evaluate them; all they would produce is a
parse error against a service whose real configuration was fine. Both
conditions have to hold, so a deployed file which is malformed for some other
reason is still uploaded and its parse error still reported. On the live
cluster this skips 14 of 532 files.

Cluster, service and role names as well as configuration file names end up
both in the path of the requests and in the paths written below the temporary
extraction folder. They are values taken from a Cloudera Manager response, so
each path segment is validated and encoded individually, and a name which
would not resolve to a location inside the extraction folder is reported and
skipped rather than requested.

## Scope of the current integration

This integration scans the cluster and reports the findings with the
affected service, role and configuration file, either at a point in time or
whenever the cluster changes.

Nothing in it sits between a configuration change and its deployment or
restart, because Cloudera Manager offers no place to sit. It provides what is
needed to *detect* a configuration change — the
[events](https://archive.cloudera.com/cm7/7.11.3.0/generic/jar/cm_api/apidocs/resource_EventsResource.html)
`coguard-cloudera-check` reads, plus the staleness state of each service —
but there is no documented pre-deployment hook that a third party could use
to block a change; detection is after the fact in every case. A gate
therefore has to sit upstream, in whatever pipeline produces the change,
which is what the exit codes of a scan and the workflow described under
[Gating a change in a pipeline](#gating-a-change-in-a-pipeline) are for.

What follows from that is a property of this integration worth stating
plainly: it can tell you that a change made the cluster worse, and it can
fail the pipeline which made it, but it cannot keep the change from reaching
the cluster in the first place. A cluster where that window has to be closed
needs the change applied to a staging cluster first.

## Planned improvements

### TODO: Kerberos (SPNEGO) authentication

Authentication currently uses a Cloudera Manager user and password, because
that is the only mechanism the Cloudera Manager API offers out of the box.
Checked against Cloudera Manager API v58: there is no API token, personal
access token, JWT or OAuth concept. None of the 282 Cloudera Manager
configuration keys refer to one, the token-shaped endpoints (`/tokens`,
`/cm/tokens`, `/users/{user}/tokens`) return `404`, and the API answers an
unauthenticated request with `WWW-Authenticate: Basic realm="Cloudera
Manager"`.

The password-free alternative is SPNEGO. Cloudera Manager can authenticate
the Admin Console *and* the API via Kerberos, controlled by the
`KRB_AUTH_ENABLE`, `KRB_AUTH_PRINCIPAL` (usually `HTTP/fqdn@REALM`) and
`KRB_AUTH_KEYTAB` settings, all of which default to off. A keytab is the
closest equivalent to a token here, with rotation handled by the KDC and no
long-lived password in an environment variable or CI secret.

Adding this should be small, since the API client already holds a
`requests.Session`: a lazily imported `requests-gssapi` dependency, a
`--cloudera-manager-kerberos` flag replacing `session.auth` with
`HTTPSPNEGOAuth`, and a password that is then no longer required. Two things
to keep in mind when it is implemented:

- `KRB_AUTH_EXCLUDE_USERS` defaults to `admin`, so the scanning identity has
  to be its own principal and Cloudera Manager user rather than `admin`.
- The machine running the CLI needs a valid ticket (`kinit`, or
  `KRB5_CLIENT_KTNAME` pointing at a keytab). This suits a CI/CD runner with
  a keytab secret better than an ad-hoc run from a workstation.

Basic authentication has to remain the default regardless, since most
Cloudera Private Cloud Base installations do not have `KRB_AUTH_ENABLE` set.

Note that CDP Public Cloud does have real API access keys, but those belong
to the CDP control plane rather than to Cloudera Manager, and are therefore
out of scope for this provider.

## FAQs

### Why is a single entry created for multiple role instances?

Roles of the same type within a role config group share their
configuration. Scanning one representative avoids reporting the same
finding once per host, while still covering every distinct configuration
in the cluster.

### Does the CLI change anything in my cluster?

Not while scanning. The scan and `coguard-cloudera-check` issue `GET` requests
only. The one thing which writes is `coguard-cloudera-banner`, and all it
writes is the `CUSTOM_BANNER_HTML` parameter of the Cloudera Manager service
configuration, i.e. the text in the header — no service configuration, and
nothing which requires a restart. It is a separate command, so a deployment
which does not run it changes nothing at all.

### The connection fails with a certificate error. What do I do?

Cloudera Manager deployments frequently sit behind a reverse proxy with a
self-signed or internal certificate. Either pass the CA bundle via
`--cloudera-manager-ca-cert`, or, for a test deployment, skip
verification with `--cloudera-manager-no-verify-tls`.

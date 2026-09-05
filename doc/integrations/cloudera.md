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

Cluster, service and role names as well as configuration file names end up
both in the path of the requests and in the paths written below the temporary
extraction folder. They are values taken from a Cloudera Manager response, so
each path segment is validated and encoded individually, and a name which
would not resolve to a location inside the extraction folder is reported and
skipped rather than requested.

## Scope of the current integration

This integration performs a scan of the cluster at a point in time, and
reports the findings with the affected service, role and configuration
file. It is a reporting and feedback mechanism.

It deliberately does not attempt to act as a gating mechanism between a
configuration change and its deployment or restart. Cloudera Manager
provides the [audits](https://archive.cloudera.com/cm7/7.11.3.0/generic/jar/cm_api/apidocs/resource_AuditsResource.html)
and events needed to *detect* a configuration change after the fact, and
continuous monitoring based on those is a natural next step, but there is
no documented pre-deployment hook that a third party could use to block a
change.

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

No. Only `GET` requests are issued.

### The connection fails with a certificate error. What do I do?

Cloudera Manager deployments frequently sit behind a reverse proxy with a
self-signed or internal certificate. Either pass the CA bundle via
`--cloudera-manager-ca-cert`, or, for a test deployment, skip
verification with `--cloudera-manager-no-verify-tls`.

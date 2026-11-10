# The Cloudera custom service descriptor

`configuration_assurance/` is a Cloudera **custom service descriptor** (CSD): a
service which can be added to a cluster in Cloudera Manager, and whose health is
the state of the configuration of that cluster. When a scan finds a High or
Critical finding that is not addressed, the service turns red in the cluster view, the health of the cluster becomes Bad, and
Cloudera Manager's own alerting fires — the same channel an operator already
watches for a datanode going down.

```
Cluster: ozone-base-cluster                Configuration Assurance   ✖ Bad Health
  ●  hdfs                                    CoGuard Configuration Check (host-1)
  ●  knox                                      Process Status            Bad
  ●  ozone                                     Unexpected Exits          Good
  ✖  Configuration Assurance                 CoGuard Report  →  the cluster's report
```

It is one service with one role, `CoGuard Configuration Check`, which runs
`coguard-cloudera-check` in a loop. The CLI it runs comes from the **COGUARD
parcel** ([`../parcel`](../parcel)): the descriptor requires the parcel tag
`coguard`, so Cloudera Manager will not start the role on a host where that parcel
is not activated, and the agent puts the parcel's `bin/` on the role's `PATH`.

What turns it red is set by `Minimum Severity`, which is `4` by default:
severities run from 1 to 5, and 4 and 5 are the High and Critical findings.
Lower findings do not make the service unhealthy, but they are still in the report
and in the banner, which counts every finding unless told otherwise.

## What Cloudera Manager can and cannot be made to show

**What a CSD can declare depends on the Cloudera Manager, not on the public
schema.** The schema in [`cloudera/cm_ext`](https://github.com/cloudera/cm_ext)
was last updated in 2016 and has no health field at all. Cloudera Manager 7 reads
more than that: its own CSDs, in `/opt/cloudera/cm/csd/` of a Cloudera Manager
7.13 host, use `healthAggregation` on their roles (272 times) and `healthTests`
with metric thresholds and messages (47 times).

This descriptor uses one of them: **`"healthAggregation": {"type": "singleton"}`**
on the CoGuard Configuration Check role, which makes the health of the service the
health of its one role. Without it, the role goes to Bad Health and the service
stays green, because a CSD service has no health test of its own and does not
otherwise look at its roles. That was observed on Cloudera Manager 7.13.2, and is
why the key is there.

What turns the role red is still **whether its process is running**: the role
stays up while the scans come back clean, and exits non-zero when a scan reports
findings at or above the configured severity, which Cloudera Manager's Process
Status test reports as Bad.

`healthTests` would allow more. It would give the service a health test of its
own, worded by us ("168 High findings"), with a yellow and a red threshold, on a
metric the role reports. The agent collects metrics for a CSD role from an HTTP
endpoint the role serves, declared in the CSD as its metrics source. That would
let the role stay up and the health clear itself once the findings are
addressed. It is not built yet.

Three things follow from the process being the signal, and they are the limits
of this integration as it is:

* **The red badge is on this service, not on the service which has the finding.**
  Cloudera Manager computes the health of `knox` from the health tests of `knox`;
  nothing installed alongside it can contribute to them. Which services are
  affected is in the role log and in the report.
* **The wording of the health test is Cloudera Manager's.** It says that a process
  exited unexpectedly, not that a Knox ACL is too permissive. The sentence about
  the findings is the first line this role logs before it exits, and it is the same
  sentence `coguard-cloudera-banner` puts into the header.
* **Red does not clear itself.** While the role is down, nothing is scanning, so a
  fixed configuration is noticed at the next start. **Restarting the role is the
  re-check**, and the first check after a start deliberately ignores the minimum
  scan interval for that reason. Turning *Automatically Restart Process* on makes
  it clear itself at the cost of a restart cycle per check interval and an
  `Unexpected Exits` test which is red as well.

## The findings in Cloudera Manager

After every scan the role prints a **CoGuard report** of the findings at or
above `Minimum Severity`, worst first, each with its severity, documentation,
remediation, sources and affected files, at the end of its stdout: on the role,
*Processes → stdout*, just above the line about the health of the service. It is
the CLI's markdown report, shown by Cloudera Manager as plain text, and the
complete output of the scan, every severity included, is above it. The
`CoGuard Report` link leads to the cluster's report in the portal.

The same report is also the role log file the descriptor declares,
`/var/log/configuration-assurance/coguard-report.md`, for reading on the host.
Cloudera Manager 7.13 does not link the role log of this role in its web
interface (*Log Files* is not offered for it), which is why the report goes into
stdout as well.

## The icon

Cloudera Manager shows a CSD's icon only if the descriptor names it: the
top-level `svgIcon` (`images/icon.svg`) and `icon` (`images/icon.png`, 16×16)
keys, as in Cloudera's own descriptors. A file in `images/` which the descriptor
does not name is ignored, and the service gets the generic Cloudera logo. The
server serves the icon itself, and generates the stylesheet rule which uses it,
from the installed jar, so a new icon needs the usual restart of the Cloudera
Manager server, and a reload of the page without the browser's cache.

## Building the jar

```shell
make csd          # from the repository root; writes dist/CONFIGURATION_ASSURANCE-1.1.jar
make parcel       # writes dist/parcel-repo/, see ../parcel/README.md
```

The jar is a zip of `descriptor/service.sdl`, `scripts/control.sh` and
`images/icon.svg` and `images/icon.png`, the CoGuard logo Cloudera Manager
shows for the service, with the
paths inside it relative to `configuration_assurance/`, and with the script
executable.

### Validating the descriptor

Cloudera ships a schema validator in
[`cloudera/cm_ext`](https://github.com/cloudera/cm_ext). It is worth running
before an installation, because the alternative place to find a mistake in the
descriptor is the log of a Cloudera Manager which has just been restarted.

The validator is a Java 6/7 project, so it neither builds nor runs on a current
JDK; a container with a JDK 8 is the short way around that:

```shell
git clone https://github.com/cloudera/cm_ext.git
docker run --rm -v "$PWD/cm_ext:/src" -w /src maven:3.9-eclipse-temurin-8 \
    mvn -B -q clean -DskipTests -DfindbugsVersion=3.0.5 -Dmaven.javadoc.skip=true install
docker run --rm -v "$PWD/cm_ext:/cm:ro" -v "$PWD/csd/configuration_assurance:/csd:ro" \
    eclipse-temurin:8-jre \
    java -jar /cm/validator/target/validator.jar -s /csd/descriptor/service.sdl
```

`-x` is strict mode, which rejects any element the schema does not know. The
descriptor in this folder fails it on purpose, on `roles.healthAggregation`
alone: that key is read by Cloudera Manager 7 but is not in the 2016 schema (see
above). Without `-x` it passes, and that is the check to run. The same validator checks the parcel, with
`-f COGUARD-<version>-el9.parcel` and `-m manifest.json`; it warns that `el9`
"does not appear to be a distro supported by CM", which is only its list of
distributions being older than RHEL 8 — Cloudera Runtime 7's own parcels are
`-el9`.

## Installing it

Installing a CSD requires a restart of the **Cloudera Manager server**. The
cluster keeps running while that happens — the services are supervised by the
agents, not by the server — but the web interface and the API are unavailable for
about a minute, and a running command in Cloudera Manager may have to be started
again.

Both files come from the [GitHub release](https://github.com/coguardio/coguard-cli/releases/latest)
of the CLI: the CSD `CONFIGURATION_ASSURANCE-<version>.jar`, and the parcel
`COGUARD-<version>-el9.parcel` with its `.sha`. Building them from a checkout
(`make parcel csd`) gives the same files in `dist/`.

1. **Install the jar and restart the Cloudera Manager server:**

   ```shell
   curl -fLO https://github.com/coguardio/coguard-cli/releases/latest/download/CONFIGURATION_ASSURANCE-1.1.jar
   scp CONFIGURATION_ASSURANCE-1.1.jar cm-host:/opt/cloudera/csd/
   ssh cm-host chown cloudera-scm:cloudera-scm /opt/cloudera/csd/CONFIGURATION_ASSURANCE-1.1.jar
   ssh cm-host chmod 644 /opt/cloudera/csd/CONFIGURATION_ASSURANCE-1.1.jar
   ssh cm-host systemctl restart cloudera-scm-server
   ```

   Then restart the **Cloudera Management Service** (*Clusters → Cloudera
   Management Service → Actions → Restart*). Its Service Monitor reads the
   service types at its start; until then it logs `Agent message has unsupported
   role type: CONFIGURATION_ASSURANCE-CONFIGURATION_CHECK`, and the service has
   no health at all. Only the monitoring roles restart, and the services of the
   cluster are not touched.

2. **Download, distribute and activate the COGUARD parcel.** The descriptor
   names the latest GitHub release as its parcel repository (`repoUrl`), and
   Cloudera Manager adds that repository to its list when it loads the CSD, so
   after the restart COGUARD is on the *Parcels* page: **Download, Distribute and
   Activate** it for the cluster. Activating it restarts nothing.

   Distribution from Cloudera Manager's own repository takes about fifteen
   minutes however small the parcel is: the agents first try to fetch it from
   each other, and only then from the Cloudera Manager server. On the test
   cluster the 22 MB parcel sat at 0 % for exactly that long and then arrived in
   seconds.

   A Cloudera Manager without access to GitHub — an air-gapped cluster, or one
   behind a proxy which does not allow it — gets the parcel into its local
   repository instead, from a machine which has access:

   ```shell
   # The version to install: the latest is the top of
   # https://github.com/coguardio/coguard-cli/releases
   version=0.3.19
   base=https://github.com/coguardio/coguard-cli/releases/download/v${version}
   parcel=COGUARD-${version}-el9.parcel
   curl -fL -O "$base/$parcel" -O "$base/$parcel.sha"
   # The .sha holds the SHA-1 alone; Cloudera Manager checks the parcel against it.
   echo "$(cat "$parcel.sha")  $parcel" | sha1sum -c -
   scp "$parcel" "$parcel.sha" cm-host:/tmp/
   ssh cm-host sudo install -m 0644 -o cloudera-scm -g cloudera-scm \
       "/tmp/$parcel" "/tmp/$parcel.sha" /opt/cloudera/parcel-repo/
   ```

   Then *Parcels → Check for New Parcels*: COGUARD shows as *Downloaded*, and is
   distributed and activated as above. The versioned address is used here
   rather than `latest/download/`, which only serves the files of the newest
   release, so a fixed version behind it stops working with the next one.

   An organization which mirrors
   `archive.cloudera.com` can mirror the release the same way: the parcel, the
   `.sha` and `manifest.json` are a complete parcel repository.

   The `latest` address only offers the newest version. To keep an older one
   available, add its own release, e.g.
   `https://github.com/coguardio/coguard-cli/releases/download/v<version>/`, under
   *Parcel Repository & Network Settings*.

3. **Have the credentials ready** for the *Add Service* wizard in step 5. They
   are parameters of the service:

   | Parameter                   | What it is                                                                 |
   |-----------------------------|----------------------------------------------------------------------------|
   | `Cloudera Manager Password` | The password of the Cloudera Manager user the scan reads the cluster as.    |
   | `CoGuard User`              | The CoGuard account the scans are made with.                               |
   | `CoGuard Password`          | Its password.                                                              |
   | `CoGuard Organization`      | The organization the scans go into, as in the portal's address: `https://portal.coguard.io/orgs/<organization>/...`. |
   | `CoGuard Cluster Name`      | The name of the cluster in the portal: its Cloudera Manager name with every character other than a letter or digit replaced by `_`, e.g. `ozone_base_cluster`. |

   The two passwords are parameters of type `password`, which Cloudera Manager
   treats as sensitive: its API, its web interface and exports of the
   configuration show them as `REDACTED`, the same as the passwords of Ranger
   or the Hive Metastore. They are handed to the role process in its
   environment, so on the host they are readable by root and by the user the
   service runs as, as any credential of a service is.

   The organization and the cluster name are required, because the role's
   `CoGuard Report` link is put together from them; Cloudera Manager can only
   substitute parameters into a link, not derive the portal's name of the
   cluster from its own. A cluster name which does not match the one the scan
   uses is not an error, but the role says in its log, after its first check,
   which value to set; with the right one it logs the address of the report.

   An organization which delivers secrets to hosts by other means -- a
   configuration management tool, a secrets agent -- can put any of them into a
   file instead, and name it as the `Credentials File` parameter. Its lines are
   `KEY=value`, with the keys `CLOUDERA_MANAGER_PASSWORD`, `COGUARD_USER_NAME`,
   `COGUARD_PASSWORD` and `COGUARD_ORGANIZATION`; a value in the file takes
   precedence over the parameter. The file is read line by line and every value
   is taken verbatim: it is not executed as shell, so a password needs no quoting
   whatever characters it contains. Quotes around a whole value are removed, so a
   file written for `source` or for systemd works as well. It has to be readable
   by `cloudera-scm`, and should be readable by nobody else:

   ```shell
   install -d -m 0750 -o cloudera-scm -g cloudera-scm /etc/coguard
   install -m 0400 -o cloudera-scm -g cloudera-scm /dev/null /etc/coguard/cloudera.env
   ```

4. **Create the working directory**, which holds the scan result and the position
   in the event feed between checks:

   ```shell
   install -d -m 0750 -o cloudera-scm -g cloudera-scm /var/lib/coguard
   ```

5. **Add the service** in Cloudera Manager: *Cluster → Add Service →
   Configuration Assurance*, assign the `CoGuard Configuration Check` role to the host
   prepared above, and fill in the Cloudera Manager URL and user and the
   credentials of step 3. That host has
   to be a host **of the cluster**, since a parcel is only distributed to those;
   the Cloudera Manager host often is not one. From a host of the cluster,
   Cloudera Manager is reachable by its internal name, e.g.
   `https://cm-host.example.internal:7183`, and with Auto-TLS the CA Certificate
   Bundle is `/var/lib/cloudera-scm-agent/agent-cert/cm-auto-global_cacerts.pem`. There is no
   dependency on another service, so the wizard is two pages.

To take it away again, stop and delete the service, remove the jar and restart the
Cloudera Manager server, then deactivate and remove the COGUARD parcel.

An upgrade of the CLI is a new parcel: activating it is picked up at the next
start of the role, which is also the next check.

## Configuration

The parameters are the options of `coguard-cloudera-check`, with the same defaults
and the same reasons for them, so the
[integration documentation](../doc/integrations/cloudera.md) covers what they mean.
The ones which are specific to running as a Cloudera service:

| Parameter                  | Default                     | What it is for                                                                                     |
|----------------------------|-----------------------------|----------------------------------------------------------------------------------------------------|
| `Cloudera Manager Password`, `CoGuard User`, `CoGuard Password`, `CoGuard Organization`, `CoGuard Cluster Name` | empty | The credentials, see *Installing it*. The passwords are redacted by Cloudera Manager. |
| `CoGuard API URL`, `CoGuard Authentication URL` | empty | A CoGuard instance of your own, e.g. `https://coguard.example.com/server` and `…/auth`. Empty is CoGuard's public instance. Set `CoGuard Portal Address` to the same instance, for the report link. |
| `Credentials File`         | empty                       | Optional: a file on the role host whose values take precedence over the credential parameters. |
| `Working Directory`        | `/var/lib/coguard`          | Where the scan result and the event watermark survive a restart of the role.                         |
| `Check Interval`           | `900`                       | How long the role waits between two checks. A check without a change does not scan.                  |
| `Minimum Severity`         | `4`                         | The lowest severity which makes the service unhealthy: High and Critical by default. Lower it to `1` to be told about every finding. |
| `Tolerated Consecutive Failures` | `3`                   | How often the check may fail to run at all before an unknown state is reported as bad health.         |
| `CoGuard Portal Address`   | `https://portal.coguard.io` | With the organization and the cluster name, becomes the `CoGuard Report` link of the role, `<address>/orgs/<organization>/<cluster name>`, since the health test cannot carry the detail.   |

The banner and the colour of the header are **not** written by this role.
`coguard-cloudera-banner` needs the Full Administrator role, whereas the scan
needs Read-Only, and giving this process an administrator password to save a
systemd unit is not a trade worth making. The two are meant to run side by side,
and both read the same `result.json` in the working directory: the role puts the
badge on the service, and the banner command puts the summary and the red header
bar in front of everybody who opens Cloudera Manager.

## Working on it

The unit tests are in `src/coguard_cli/tests/cloudera_integration/`:
`csd_test.py` checks the descriptor against itself, `control.sh`, the Makefile
and the icons, and runs `control.sh` under bash against a stand-in for the
check; `build_parcel_test.py` covers the parcel build, with pip replaced. They
run with the rest of the suite (`cd src && pytest`).

`scripts/control.sh` is checked with `bash -n` and `shellcheck`, and can be
exercised without a cluster by putting a fake check command on the `PATH`:

```shell
work=$(mktemp -d)
printf 'CLOUDERA_MANAGER_PASSWORD=whatever\nCOGUARD_USER_NAME=someone\nCOGUARD_PASSWORD=whatever\n' > "$work/cloudera.env"
chmod 0400 "$work/cloudera.env"
# Stands in for `coguard-cloudera-check`, and exits the way the check does with
# --exit-with-last-scan: 0 clean, 1 findings, 2 the check could not be performed.
printf '#!/usr/bin/env bash\nexit "${FAKE_CHECK_EXIT:-0}"\n' > "$work/fake-check"
chmod +x "$work/fake-check"
env CLOUDERA_MANAGER_URL=https://cm.example.com CHECK_EXECUTABLE="$work/fake-check" \
    COGUARD_EXECUTABLE=true ENVIRONMENT_FILE="$work/cloudera.env" WORK_DIRECTORY="$work" \
    CHECK_INTERVAL_SECONDS=1 FAKE_CHECK_EXIT=1 \
    bash csd/configuration_assurance/scripts/control.sh start
echo "exit code: $?"   # 1, i.e. what Cloudera Manager reports as bad health
```

The three outcomes worth exercising are a scan with findings (exit `1`), a stop
requested with `SIGTERM` while clean (exit `0`), and a check which cannot run at
all more often than the tolerance (exit `2`).

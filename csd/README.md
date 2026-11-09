# The Cloudera custom service descriptor

`configuration_assurance/` is a Cloudera **custom service descriptor** (CSD): a
service which can be added to a cluster in Cloudera Manager, and whose health is
the state of the configuration of that cluster. When a scan finds a High or
Critical finding that is not addressed, the service turns red in the cluster view, the health of the cluster becomes Bad, and
Cloudera Manager's own alerting fires — the same channel an operator already
watches for a datanode going down.

```
Cluster: ozone-base-cluster                Configuration Assurance   ✖ Bad Health
  ●  hdfs                                    Configuration Check (host-1)
  ●  knox                                      Process Status            Bad
  ●  ozone                                     Unexpected Exits          Good
  ✖  Configuration Assurance                 Configuration Report  →  portal
```

It is one service with one role, `Configuration Check`, which runs
`coguard-cloudera-check` in a loop. The CLI it runs comes from the **COGUARD
parcel** ([`../parcel`](../parcel)): the descriptor requires the parcel tag
`coguard`, so Cloudera Manager will not start the role on a host where that parcel
is not activated, and the agent puts the parcel's `bin/` on the role's `PATH`.

What turns it red is set by `Minimum Severity`, which is `4` by default:
severities run from 1 to 5, and 4 and 5 are the High and Critical findings.
Lower findings do not make the service unhealthy, but they are still in the report
and in the banner, which counts every finding unless told otherwise.

## What Cloudera Manager can and cannot be made to show

**A CSD cannot declare a health test.** This is worth stating plainly, because
the wiki of `cloudera/cm_ext` suggests otherwise. There is no health field in the
schema: neither `ServiceDescriptor` nor `RoleDescriptor` has one, Cloudera's own
every-field fixtures (`service_full.sdl`, `service_full.mdl`) contain neither a
health nor a threshold key, and the metric definitions of an MDL are names, labels
and units without a type or a green/yellow/red range. A CSD-based service gets the
health tests Cloudera Manager generates for every service — `Process Status`,
`Unexpected Exits`, `File Descriptors`, `Host Health`, `Log Directory Free Space`,
`Swap Memory Usage` — and one aggregate per role type.

The one signal a CSD can therefore move is **whether its own role process is
running**, and that is what this descriptor uses: the role stays up while the
cluster's configuration comes back clean, and exits non-zero when a scan reports
findings at or above the configured severity.

Three things follow, and they are the honest limits of this integration:

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

## Building the jar

```shell
make csd          # from the repository root; writes dist/CONFIGURATION_ASSURANCE-1.1.jar
make parcel       # writes dist/parcel-repo/, see ../parcel/README.md
```

The jar is a zip of `descriptor/service.sdl` and `scripts/control.sh`, with the
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
    java -jar /cm/validator/target/validator.jar -s /csd/descriptor/service.sdl -x
```

`-x` is strict mode, which rejects any element the schema does not know. The
descriptor in this folder passes it. The same validator checks the parcel, with
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

2. **Download, distribute and activate the COGUARD parcel.** The descriptor
   names the latest GitHub release as its parcel repository (`repoUrl`), and
   Cloudera Manager adds that repository to its list when it loads the CSD, so
   after the restart COGUARD is on the *Parcels* page: **Download, Distribute and
   Activate** it for the cluster. Activating it restarts nothing.

   A Cloudera Manager without access to GitHub — an air-gapped cluster, or one
   behind a proxy which does not allow it — gets the parcel into its local
   repository instead, from a machine which has access:

   ```shell
   base=https://github.com/coguardio/coguard-cli/releases/latest/download
   curl -fL -O "$base/COGUARD-0.3.18-el9.parcel" -O "$base/COGUARD-0.3.18-el9.parcel.sha"
   scp COGUARD-0.3.18-el9.parcel* cm-host:/opt/cloudera/parcel-repo/
   ssh cm-host chown cloudera-scm:cloudera-scm '/opt/cloudera/parcel-repo/COGUARD-*'
   ```

   and then *Parcels → Check for New Parcels*. An organization which mirrors
   `archive.cloudera.com` can mirror the release the same way: the parcel, the
   `.sha` and `manifest.json` are a complete parcel repository.

   The `latest` address only offers the newest version. To keep an older one
   available, add its own release, e.g.
   `https://github.com/coguardio/coguard-cli/releases/download/v0.3.18/`, under
   *Parcel Repository & Network Settings*.

3. **Write the credentials file**, `/etc/coguard/cloudera.env`, holding the
   password of the Cloudera Manager user the scan authenticates as and the CoGuard
   account. It is read by the role process, and by nothing else:

   ```shell
   install -d -m 0750 -o cloudera-scm -g cloudera-scm /etc/coguard
   install -m 0400 -o cloudera-scm -g cloudera-scm /dev/null /etc/coguard/cloudera.env
   cat > /etc/coguard/cloudera.env <<'EOF'
   CLOUDERA_MANAGER_PASSWORD=...
   COGUARD_USER_NAME=...
   COGUARD_PASSWORD=...
   # Only if the CoGuard account has more than one organization.
   COGUARD_ORGANIZATION=...
   EOF
   ```

   The passwords are deliberately not parameters of the service: a parameter is
   stored in the Cloudera Manager database, is readable through its API by anybody
   who can read the service configuration, and shows up in a configuration
   revision event.

   `COGUARD_ORGANIZATION` is not a secret and is only there because it belongs
   with the account: when a CoGuard account has several organizations, the CLI
   asks which one a scan belongs to, and this role has nobody to ask. Without it
   the scan of such an account stops and names the organizations it could have
   used, which the role reports as a failed check rather than as findings.

4. **Create the working directory**, which holds the scan result and the position
   in the event feed between checks:

   ```shell
   install -d -m 0750 -o cloudera-scm -g cloudera-scm /var/lib/coguard
   ```

5. **Add the service** in Cloudera Manager: *Cluster → Add Service →
   Configuration Assurance*, assign the `Configuration Check` role to the host
   prepared above, and fill in the Cloudera Manager URL and user. There is no
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
| `Credentials File`         | `/etc/coguard/cloudera.env` | Where the passwords come from, so that they are not in Cloudera Manager's database.                 |
| `Working Directory`        | `/var/lib/coguard`          | Where the scan result and the event watermark survive a restart of the role.                         |
| `Check Interval`           | `900`                       | How long the role waits between two checks. A check without a change does not scan.                  |
| `Minimum Severity`         | `4`                         | The lowest severity which makes the service unhealthy: High and Critical by default. Lower it to `1` to be told about every finding. |
| `Tolerated Consecutive Failures` | `3`                   | How often the check may fail to run at all before an unknown state is reported as bad health.         |
| `Python Interpreter`       | `coguard-python`            | Used to read the outcome of the last scan. The default is the parcel's, which can import the CLI, so the role log names the affected services. |
| `Report Address`           | `https://portal.coguard.io` | Becomes the `Configuration Report` link of the role, since the health test cannot carry the detail.   |

The banner and the colour of the header are **not** written by this role.
`coguard-cloudera-banner` needs the Full Administrator role, whereas the scan
needs Read-Only, and giving this process an administrator password to save a
systemd unit is not a trade worth making. The two are meant to run side by side,
and both read the same `result.json` in the working directory: the role puts the
badge on the service, and the banner command puts the summary and the red header
bar in front of everybody who opens Cloudera Manager.

## Working on it

`scripts/control.sh` is checked with `bash -n` and `shellcheck`, and can be
exercised without a cluster by putting a fake check command on the `PATH`:

```shell
work=$(mktemp -d)
printf 'CLOUDERA_MANAGER_PASSWORD=whatever\n' > "$work/cloudera.env"
chmod 0400 "$work/cloudera.env"
# Stands in for `coguard-cloudera-check`: records the outcome of a scan in the
# state file it was given, and exits the way the check would.
cat > "$work/fake-check" <<'EOF'
#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
  [ "$1" = "--state-file" ] && state_file=$2
  shift
done
python3 -c 'import json, sys; json.dump({"lastScanExitCode": int(sys.argv[2])}, open(sys.argv[1], "w"))' \
    "$state_file" "${FAKE_SCAN_EXIT:-0}"
exit "${FAKE_CHECK_EXIT:-0}"
EOF
chmod +x "$work/fake-check"
env CLOUDERA_MANAGER_URL=https://cm.example.com CHECK_EXECUTABLE="$work/fake-check" \
    ENVIRONMENT_FILE="$work/cloudera.env" WORK_DIRECTORY="$work" \
    PYTHON_EXECUTABLE=python3 CHECK_INTERVAL_SECONDS=1 FAKE_SCAN_EXIT=1 \
    bash csd/configuration_assurance/scripts/control.sh start
echo "exit code: $?"   # 1, i.e. what Cloudera Manager reports as bad health
```

The three outcomes worth exercising are a scan with findings (exit `1`), a stop
requested with `SIGTERM` while clean (exit `0`), and a check which cannot run at
all more often than the tolerance (exit `2`).

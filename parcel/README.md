# The COGUARD parcel

A **parcel** is how Cloudera Manager puts software onto the hosts of a cluster:
an archive it downloads from a repository, distributes to the hosts, and
activates, with a version which can be rolled forward and back from the
*Parcels* page. This folder builds one which holds the CoGuard CLI and
everything it depends on, so that installing CoGuard on a cluster is the same
operation as installing any other Cloudera component, and not a `pip install`
on a host somebody has to log into.

It is what the [Configuration Assurance CSD](../csd) runs: the descriptor
requires the parcel tag `coguard`, which this parcel provides. That service is
unhealthy while a High or Critical finding is not addressed; see
[`../csd/README.md`](../csd/README.md).

## Building it

```shell
make parcel                                   # from the repository root
make parcel PARCEL_OPTIONS="--distro el8 --python-version 3.11"
make parcel PARCEL_OPTIONS="--version 0.3.17.1"    # a test build of an installed version
```

This writes a parcel repository into `dist/parcel-repo/`:

```
dist/parcel-repo/
    COGUARD-0.3.18-el9.parcel        the parcel
    COGUARD-0.3.18-el9.parcel.sha    its SHA-1, for a local parcel-repo directory
    manifest.json                    what a remote repository is read through
```

The version is the one in `setup.cfg`. The parcel contains no interpreter: it
runs on the Python of the host, and its libraries are built for exactly one
version of it, because `cryptography`, `cffi` and `pyyaml` have compiled parts.
The default is `3.9` and `el9`, i.e. the system Python of RHEL 9 and its
derivatives. RHEL 8's system Python is 3.6, which the CLI does not support, so
an `el8` parcel needs a newer Python on the hosts (`dnf install python3.11`) and
`--python-version 3.11`.

The wheels are fetched by pip for the target platform (`manylinux`, x86_64), so
the build runs on any machine with access to PyPI and needs no container of the
target distribution.

## What is in it

```
COGUARD-<version>/
    meta/parcel.json          name, version, and the tag `coguard` it provides
    meta/coguard_env.sh       sourced by the agent: sets COGUARD_HOME, and puts
                              bin/ on the PATH of the processes using the parcel
    lib/python/               coguard_cli and its dependencies
    bin/coguard               \
    bin/coguard-cloudera-check  > the entry points of the CLI
    bin/coguard-cloudera-banner/
```

Each script in `bin/` runs `python3.<minor>` of the host with `lib/python` on
`PYTHONPATH`. `COGUARD_PYTHON` overrides the interpreter where it is not on the
`PATH` by that name.

The commands can be used from a shell on any host the parcel is active on, which
is how `coguard-cloudera-banner` is meant to be run, since it needs a Full
Administrator account the service does not hold:

```shell
/opt/cloudera/parcels/COGUARD/bin/coguard-cloudera-banner --help
```

## Installing it

Customers do not build the parcel; it is an asset of every
[GitHub release](https://github.com/coguardio/coguard-cli/releases), along with
its `.sha`, `manifest.json` and the CSD jar. The CSD names
`https://github.com/coguardio/coguard-cli/releases/latest/download/` as its parcel
repository, so once the jar is installed COGUARD appears on the *Parcels* page by
itself. The steps, including the one for a Cloudera Manager without access to
GitHub, are in [`../csd/README.md`](../csd/README.md#installing-it).

A parcel built from a checkout is installed the same way as one downloaded,
by copying it and its `.sha` into `/opt/cloudera/parcel-repo/` on the Cloudera
Manager host, or by serving `dist/parcel-repo/` from any web server and adding
its address under *Parcels → Parcel Repository & Network Settings*.

## Releasing it

The workflow [`github_release.yml`](../.github/workflows/github_release.yml) is
run by hand, like the PyPI upload, once the version in `setup.cfg` is the one to
release. It builds the parcel and the CSD, tries the parcel on RHEL 9's own
Python in a UBI 9 container, and creates the release `v<version>` with the four
files. It refuses to replace a release which exists: a rebuilt parcel has a
different hash than the `.sha` customers already have.

Because the CSD reads its parcel from the *latest* release, every release from
here on has to be made by that workflow, or carry the same files; a release
without them would make the `latest` address an empty parcel repository.

## Validating it

Cloudera's validator in [`cloudera/cm_ext`](https://github.com/cloudera/cm_ext)
checks the parcel and the manifest; how to build it is in
[`../csd/README.md`](../csd/README.md#validating-the-descriptor).

```shell
java -jar validator.jar -f dist/parcel-repo/COGUARD-0.3.18-el9.parcel
java -jar validator.jar -m dist/parcel-repo/manifest.json
```

The warning that `el9` "does not appear to be a distro supported by CM" comes
from a list of distributions last updated in 2016, which does not have `el8`
either; Cloudera Runtime 7's own parcels are `-el9`.

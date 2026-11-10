#!/usr/bin/env python3
"""
Builds the COGUARD parcel: the CoGuard CLI, with every dependency it has, in the
form Cloudera Manager distributes software to the hosts of a cluster.

    python3 parcel/build_parcel.py                    # from the repository root
    python3 parcel/build_parcel.py --distro el8 --python-version 3.11

The output is a parcel repository in `dist/parcel-repo/`: the parcel, its
`.sha` file and a `manifest.json`. That directory can be served by any web
server and added under *Parcel Repository & Network Settings*, or its parcel
and `.sha` can be copied into `/opt/cloudera/parcel-repo/` on the Cloudera
Manager host.

The parcel does not contain an interpreter. It runs on the Python of the host,
and contains the libraries built for exactly one version of it, which is why
that version is part of what is built: the hosts of a RHEL 9 cluster have
3.9, and `cryptography`, `cffi` and `pyyaml` have compiled parts which only load
into the interpreter they were built for. The wheels are fetched for that
platform by pip, so the parcel can be built on any machine with network access,
without a container of the target distribution.

Why this is Python and not a shell script: the build cannot do without Python
anyway, because the parcel is made of wheels which pip fetches for the hosts'
platform and interpreter. What it does besides calling pip is what a shell
script does badly or not portably. It reads the version and the multi-line
dependency list from setup.cfg (configparser, rather than grepping an INI
value). It writes two JSON files, meta/parcel.json and manifest.json (json,
rather than hand-escaped heredocs or a dependency on jq). It packs a tar whose
files belong to root whoever builds it (tarfile, the same everywhere, where
GNU tar's --owner/--group is not accepted by the bsdtar of macOS). And it
hashes the result. Everything else in this repository is Python, linted and
tested the same way.

What is in it:

    COGUARD-<version>/
        meta/parcel.json         what Cloudera Manager reads about the parcel
        meta/coguard_env.sh      puts bin/ on the PATH of the processes using it
        lib/python/              coguard_cli and its dependencies
        bin/coguard              the entry points, as wrappers which run the
        bin/coguard-cloudera-check   host's python3.<minor> with lib/python on
        bin/coguard-cloudera-banner  the module path
"""

import argparse
import configparser
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
SETUP_CFG = REPOSITORY_ROOT / "setup.cfg"
ENVIRONMENT_SCRIPT = Path(__file__).resolve().parent / "meta" / "coguard_env.sh"

# The name of the parcel and the tag it provides. The CSD requires the tag, not
# the name, which is the convention of Cloudera's own parcels and keeps the two
# independent of each other.
PARCEL_NAME = "COGUARD"
PARCEL_TAG = "coguard"

# The entry points of the CLI which a host of the cluster has a use for, and the
# function each of them runs. The Coverity translator is left out: it is not part
# of the `coguard_cli` package, and has nothing to do with a cluster.
ENTRY_POINTS = {
    "coguard": "coguard_cli.__main__:main",
    "coguard-cloudera-check": "coguard_cli.cloudera_integration.check:main",
    "coguard-cloudera-banner": "coguard_cli.cloudera_integration.banner:main",
}

# The platforms pip may take a wheel for. manylinux_2_28 is RHEL 8 and later;
# manylinux2014 (glibc 2.17) is what the older wheels of the dependencies are.
PLATFORMS = (
    "manylinux_2_28_x86_64",
    "manylinux_2_17_x86_64",
    "manylinux2014_x86_64",
)

WRAPPER_TEMPLATE = """#!/usr/bin/env bash
# {name}, from the {parcel} parcel. The libraries in lib/python are built for
# Python {python_version}, so that is the interpreter this runs on; COGUARD_PYTHON
# overrides it for a host where it is somewhere other than on the PATH.
here=$(cd "$(dirname "$(readlink -f "${{BASH_SOURCE[0]}}")")" && pwd)
export PYTHONPATH="${{here}}/../lib/python${{PYTHONPATH:+:${{PYTHONPATH}}}}"
{command}
"""

# `python -c` puts the current directory first on the module path, ahead of
# PYTHONPATH, so a `coguard_cli` directory wherever the command is run from would
# be imported instead of the parcel's. The first entry is therefore dropped
# before anything is imported; `-P` would do the same, but only from Python 3.11.
ENTRY_POINT_COMMAND = (
    'exec "${{COGUARD_PYTHON:-python{python_version}}}" -c '
    "'import sys; sys.path.pop(0); sys.argv[0] = sys.argv.pop(1); "
    "from {module} import {function}; sys.exit({function}())' "
    '{name} "$@"'
)


def cli_version() -> str:
    """The version of the CLI in this checkout, which the parcel is versioned by."""
    parser = configparser.ConfigParser()
    parser.read(SETUP_CFG)
    return parser.get("metadata", "version").strip()


def cli_requirements():
    """The run-time requirements of the CLI, as `setup.cfg` lists them."""
    parser = configparser.ConfigParser()
    parser.read(SETUP_CFG)
    return [
        line.strip()
        for line in parser.get("options", "install_requires").splitlines()
        if line.strip()
    ]


def pip(*arguments: str) -> None:
    """Runs pip of the interpreter this script runs on."""
    subprocess.run(
        [sys.executable, "-m", "pip", "--disable-pip-version-check",
         "--no-input", "--quiet", *arguments],
        check=True,
    )


def install_libraries(target: Path, python_version: str, wheel: Path) -> None:
    """
    Installs the CLI and its dependencies into `target`, built for
    `python_version` on x86_64 Linux. The CLI itself is pure Python and installed
    without the platform restriction, which pip only allows for binary
    distributions; its dependencies are then resolved for the target platform,
    with `--only-binary` so that nothing is compiled for the machine this runs
    on by mistake.
    """
    pip("install", "--no-deps", "--no-compile", "--target", str(target), str(wheel))
    abi = "cp" + python_version.replace(".", "")
    platform_options = [option for platform in PLATFORMS
                        for option in ("--platform", platform)]
    pip("install", "--no-compile", "--no-warn-conflicts", "--upgrade",
        "--target", str(target),
        "--python-version", python_version,
        "--implementation", "cp",
        "--abi", abi, "--abi", "abi3", "--abi", "none",
        *platform_options, "--platform", "any",
        "--only-binary=:all:",
        *cli_requirements())
    # pip --target puts the console scripts of the dependencies into bin/ of the
    # target, with the interpreter of this machine in their first line. None of
    # them is needed, and they would not run on a host of the cluster.
    shutil.rmtree(target / "bin", ignore_errors=True)
    # A `.pth` file is only processed in a site directory, and lib/python is put
    # on PYTHONPATH instead, so the one setuptools ships would do nothing there.
    for path_file in target.glob("*.pth"):
        path_file.unlink()


def build_wheel(output: Path) -> Path:
    """Builds the wheel of the CLI in this checkout, without its dependencies."""
    pip("wheel", "--no-deps", "--wheel-dir", str(output), str(REPOSITORY_ROOT))
    wheels = sorted(output.glob("coguard_cli-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one wheel of the CLI in {output}, found {wheels}")
    return wheels[0]


def write_wrappers(bin_directory: Path, python_version: str) -> None:
    """Writes the entry points into `bin/`."""
    bin_directory.mkdir(parents=True)
    commands = {
        name: ENTRY_POINT_COMMAND.format(
            python_version=python_version,
            module=target.split(":")[0],
            function=target.split(":")[1],
            name=name,
        )
        for name, target in ENTRY_POINTS.items()
    }
    for name, command in commands.items():
        wrapper = bin_directory / name
        wrapper.write_text(WRAPPER_TEMPLATE.format(name=name,
                                                   parcel=PARCEL_NAME,
                                                   python_version=python_version,
                                                   command=command),
                           encoding="utf-8")
        wrapper.chmod(0o755)


def components(version: str):
    """The components of the parcel, as parcel.json and manifest.json list them."""
    return [{"name": "coguard-cli", "version": version, "pkg_version": version}]


def parcel_descriptor(version: str) -> dict:
    """
    The content of meta/parcel.json. The schema is the one of
    cloudera/cm_ext; `provides` is the tag the Configuration Assurance CSD
    requires, and `scripts.defines` the script the agent sources before it
    starts a process of a service which requires that tag.
    """
    return {
        "schema_version": 1,
        "name": PARCEL_NAME,
        "version": version,
        "setActiveSymlink": True,
        "depends": "",
        "replaces": "",
        "conflicts": "",
        "provides": [PARCEL_TAG],
        "scripts": {"defines": ENVIRONMENT_SCRIPT.name},
        "packages": [{"name": "coguard-cli", "version": version}],
        "components": components(version),
        "users": {},
        "groups": [],
    }


def owned_by_root(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """
    The files of a parcel are root's on the hosts; the agent unpacks the
    archive as root and keeps the ownership in it, so it is set here rather
    than inherited from whoever builds the parcel.
    """
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    return info


def write_parcel(staging: Path, parcel_file: Path) -> None:
    """Packs the staged parcel directory into a gzip-compressed tar."""
    with tarfile.open(parcel_file, "w:gz") as archive:
        archive.add(staging, arcname=staging.name, filter=owned_by_root)


def sha1_of(path: Path) -> str:
    """The SHA-1 of a file, which is the hash Cloudera Manager checks a parcel by."""
    digest = hashlib.sha1()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(repository: Path) -> None:
    """
    Writes manifest.json, listing every parcel in the repository directory, so
    that the builds for several distributions, and earlier versions kept for a
    rollback, are one repository. The version of a parcel is the part of its
    name between the first and the last dash.
    """
    parcels = []
    for parcel_file in sorted(repository.glob(f"{PARCEL_NAME}-*.parcel")):
        version = parcel_file.name[len(PARCEL_NAME) + 1:].rsplit("-", 1)[0]
        parcels.append({
            "parcelName": parcel_file.name,
            "components": components(version),
            "hash": sha1_of(parcel_file),
        })
    manifest = {"lastUpdated": int(time.time() * 1000), "parcels": parcels}
    (repository / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                              encoding="utf-8")


def parse_arguments(argv):
    """The command line of this script."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--distro", action="append", dest="distros",
                        help=("The distribution suffix of the parcel, e.g. el9. "
                              "May be given more than once for distributions "
                              "with the same Python. Defaults to el9."))
    parser.add_argument("--python-version", default="3.9",
                        help=("The Python of the hosts the parcel is for, as "
                              "major.minor. Defaults to 3.9, the system Python "
                              "of RHEL 9."))
    parser.add_argument("--version",
                        help=("The version of the parcel. Defaults to the "
                              "version of the CLI in setup.cfg; a different one "
                              "is for a test or a rebuild of an installed version, "
                              "e.g. 0.3.17.1, since Cloudera Manager does not "
                              "redistribute a version which is already "
                              "activated. Must not contain a dash."))
    parser.add_argument("--wheel", type=Path,
                        help=("A wheel of the CLI to put into the parcel. "
                              "Defaults to building one from this checkout."))
    parser.add_argument("--output", type=Path,
                        default=REPOSITORY_ROOT / "dist" / "parcel-repo",
                        help="The parcel repository directory to write into.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    """Builds the parcel and writes it into the parcel repository directory."""
    args = parse_arguments(argv)
    distros = args.distros or ["el9"]
    version = args.version or cli_version()
    if "-" in version:
        print(f"The version {version} contains a dash, which would make the name "
              "of the parcel ambiguous.", file=sys.stderr)
        return 1
    if args.wheel and not args.version and f"-{version}-" not in args.wheel.name:
        print(f"The wheel {args.wheel.name} is not version {version} of the CLI, "
              "which is the version the parcel is named by.", file=sys.stderr)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        wheel = args.wheel or build_wheel(temporary / "wheel")
        staging = temporary / f"{PARCEL_NAME}-{version}"
        install_libraries(staging / "lib" / "python", args.python_version, wheel)
        write_wrappers(staging / "bin", args.python_version)
        (staging / "meta").mkdir()
        shutil.copy2(ENVIRONMENT_SCRIPT, staging / "meta" / ENVIRONMENT_SCRIPT.name)
        (staging / "meta" / "parcel.json").write_text(
            json.dumps(parcel_descriptor(version), indent=2) + "\n", encoding="utf-8")
        for distro in distros:
            parcel_file = args.output / f"{PARCEL_NAME}-{version}-{distro}.parcel"
            write_parcel(staging, parcel_file)
            Path(f"{parcel_file}.sha").write_text(sha1_of(parcel_file),
                                                  encoding="utf-8")
            print(f"Built {parcel_file}")
    write_manifest(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

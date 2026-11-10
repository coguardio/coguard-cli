"""
Tests of parcel/build_parcel.py, the build of the COGUARD parcel.

The script is not part of the package, so it is loaded from the checkout. pip is
never run: the two steps which call it are replaced by stand-ins, so that the
tests need no network and no wheels for another platform.
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
import unittest.mock

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[4]
BUILD_SCRIPT = REPOSITORY_ROOT / "parcel" / "build_parcel.py"


def load_build_script():
    """Loads parcel/build_parcel.py as a module."""
    spec = importlib.util.spec_from_file_location("build_parcel", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# A stand-in for the CLI in lib/python of the parcel: every entry point prints
# its program name and its arguments, and exits with the number of arguments.
FAKE_ENTRY_POINT = '''
import sys


def main():
    print(sys.argv[0], *sys.argv[1:])
    return len(sys.argv) - 1
'''


def fake_install_libraries(target, python_version, wheel):  # pylint: disable=unused-argument
    """Puts a stand-in for the CLI where install_libraries would put the real one."""
    for module in ("coguard_cli/__main__.py",
                   "coguard_cli/cloudera_integration/check.py",
                   "coguard_cli/cloudera_integration/banner.py"):
        path = pathlib.Path(target) / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FAKE_ENTRY_POINT, encoding="utf-8")
    for package in ("coguard_cli", "coguard_cli/cloudera_integration"):
        (pathlib.Path(target) / package / "__init__.py").touch()


@unittest.skipUnless(BUILD_SCRIPT.is_file(), "Only applicable to a source checkout.")
class TestBuildParcel(unittest.TestCase):
    """
    The class for testing the build of the COGUARD parcel.
    """

    @classmethod
    def setUpClass(cls):
        cls.build = load_build_script()

    def build_parcel(self, output, argv=()):
        """Runs main() with pip replaced, and returns its exit code."""
        with unittest.mock.patch.object(self.build, "build_wheel",
                                        return_value=pathlib.Path("coguard_cli-x.whl")), \
             unittest.mock.patch.object(self.build, "install_libraries",
                                        side_effect=fake_install_libraries), \
             unittest.mock.patch("builtins.print"):
            return self.build.main(["--output", str(output), *argv])

    def test_version_and_requirements_come_from_setup_cfg(self):
        """
        The parcel is versioned by the CLI, and gets the CLI's dependencies.
        """
        self.assertRegex(self.build.cli_version(), r"^\d+\.\d+\.\d+$")
        requirements = self.build.cli_requirements()
        self.assertIn("requests", requirements)
        self.assertTrue(all(requirement.strip() == requirement and requirement
                            for requirement in requirements))

    def test_parcel_descriptor(self):
        """
        meta/parcel.json provides the tag the CSD requires, and names the
        environment script which is shipped next to it.
        """
        descriptor = self.build.parcel_descriptor("1.2.3")
        self.assertEqual(descriptor["name"], "COGUARD")
        self.assertEqual(descriptor["version"], "1.2.3")
        self.assertEqual(descriptor["provides"], ["coguard"])
        self.assertTrue(descriptor["setActiveSymlink"])
        self.assertTrue((BUILD_SCRIPT.parent / "meta" / descriptor["scripts"]["defines"]).is_file())
        sdl = json.loads((REPOSITORY_ROOT / "csd" / "configuration_assurance" / "descriptor"
                          / "service.sdl").read_text(encoding="utf-8"))
        self.assertEqual(sdl["parcel"]["requiredTags"], descriptor["provides"])

    def test_install_libraries(self):
        """
        The CLI is installed without its dependencies, and the dependencies as
        binary wheels for the target Python on manylinux only; the console
        scripts of the dependencies and the .pth files are removed.
        """
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / "lib"

            def fake_pip(command, check):  # pylint: disable=unused-argument
                (target / "bin").mkdir(parents=True, exist_ok=True)
                (target / "bin" / "normalizer").touch()
                (target / "distutils-precedence.pth").touch()

            with unittest.mock.patch.object(self.build.subprocess, "run",
                                            side_effect=fake_pip) as run:
                self.build.install_libraries(target, "3.9", pathlib.Path("cli.whl"))
            self.assertEqual(sorted(os.listdir(target)), [])
        first, second = (call.args[0] for call in run.call_args_list)
        self.assertIn("--no-deps", first)
        self.assertEqual(first[-1], "cli.whl")
        self.assertIn("--only-binary=:all:", second)
        self.assertEqual(second[second.index("--python-version") + 1], "3.9")
        self.assertIn("cp39", second)
        self.assertIn("manylinux2014_x86_64", second)
        self.assertNotIn("--no-deps", second)

    def test_build(self):
        """
        A build writes the parcel, its .sha and the manifest; the parcel is one
        directory named after name and version, owned by root, with the meta
        files and an executable wrapper per entry point.
        """
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            self.assertEqual(self.build_parcel(output, ["--version", "1.2.3.4"]), 0)
            parcel = output / "COGUARD-1.2.3.4-el9.parcel"
            self.assertEqual(sorted(path.name for path in output.iterdir()),
                             ["COGUARD-1.2.3.4-el9.parcel", "COGUARD-1.2.3.4-el9.parcel.sha",
                              "manifest.json"])
            sha = (output / "COGUARD-1.2.3.4-el9.parcel.sha").read_text(encoding="utf-8")
            self.assertEqual(sha, self.build.sha1_of(parcel))
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["parcels"][0]["parcelName"], parcel.name)
            self.assertEqual(manifest["parcels"][0]["hash"], sha)
            self.assertEqual(manifest["parcels"][0]["components"][0]["version"], "1.2.3.4")
            with tarfile.open(parcel) as archive:
                members = archive.getmembers()
                names = {member.name for member in members}
                parcel_json = json.load(archive.extractfile("COGUARD-1.2.3.4/meta/parcel.json"))
                wrapper = archive.getmember("COGUARD-1.2.3.4/bin/coguard-cloudera-check")
        self.assertTrue(all(name == "COGUARD-1.2.3.4" or name.startswith("COGUARD-1.2.3.4/")
                            for name in names))
        self.assertTrue(all(member.uid == 0 and member.gid == 0 and member.uname == "root"
                            for member in members))
        for name in ("meta/parcel.json", "meta/coguard_env.sh", "bin/coguard",
                     "bin/coguard-cloudera-check", "bin/coguard-cloudera-banner"):
            self.assertIn(f"COGUARD-1.2.3.4/{name}", names)
        self.assertNotIn("COGUARD-1.2.3.4/bin/coguard-python", names)
        self.assertEqual(parcel_json["version"], "1.2.3.4")
        self.assertTrue(wrapper.mode & 0o111)

    def test_wrapper_runs_the_entry_point(self):
        """
        A wrapper runs its entry point from lib/python, under its own name, with
        the arguments unchanged, and exits with its exit code -- also when it is
        run from a directory with a `coguard_cli` of its own in it, which `python
        -c` would otherwise import first.
        """
        with tempfile.TemporaryDirectory() as directory:
            staging = pathlib.Path(directory) / "COGUARD-1.0"
            fake_install_libraries(staging / "lib" / "python", "3.9", None)
            self.build.write_wrappers(staging / "bin", "3.9")
            decoy = pathlib.Path(directory) / "elsewhere" / "coguard_cli" / "cloudera_integration"
            decoy.mkdir(parents=True)
            (decoy.parent / "__init__.py").touch()
            (decoy / "__init__.py").touch()
            (decoy / "check.py").write_text("def main():\n    print('decoy')\n    return 9\n",
                                            encoding="utf-8")
            environment = {key: value for key, value in os.environ.items()
                           if key != "PYTHONPATH"}
            completed = subprocess.run(
                [str(staging / "bin" / "coguard-cloudera-check"), "--a", "b c"],
                env=dict(environment, COGUARD_PYTHON=sys.executable),
                cwd=decoy.parent.parent, capture_output=True, text=True, check=False
            )
        self.assertEqual(completed.stderr, "")
        self.assertEqual(completed.stdout.strip(), "coguard-cloudera-check --a b c")
        self.assertEqual(completed.returncode, 2)

    def test_manifest_lists_every_version(self):
        """
        The manifest lists every parcel of the directory under its own version,
        so that earlier versions kept for a rollback stay installable.
        """
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            self.build_parcel(output, ["--version", "1.0"])
            self.build_parcel(output, ["--version", "1.0.1"])
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {(entry["parcelName"], entry["components"][0]["version"])
             for entry in manifest["parcels"]},
            {("COGUARD-1.0-el9.parcel", "1.0"), ("COGUARD-1.0.1-el9.parcel", "1.0.1")}
        )

    def test_a_version_with_a_dash_is_refused(self):
        """
        A dash in the version would make the parcel's name ambiguous.
        """
        with tempfile.TemporaryDirectory() as directory, \
             unittest.mock.patch("sys.stderr"):
            self.assertEqual(self.build_parcel(pathlib.Path(directory), ["--version", "1.0-1"]),
                             1)
            self.assertEqual(os.listdir(directory), [])

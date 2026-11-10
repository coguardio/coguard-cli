"""
Tests of the Configuration Assurance CSD in csd/configuration_assurance: the
consistency of its descriptor, and the behaviour of scripts/control.sh, the
process Cloudera Manager supervises for the CoGuard Configuration Check role.

control.sh is run under bash against a stand-in for `coguard-cloudera-check`,
which records the arguments and the environment it was started with and exits
with the code it is told to.
"""

import json
import os
import pathlib
import re
import shutil
import signal
import struct
import subprocess
import tempfile
import time
import unittest

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[4]
CSD = REPOSITORY_ROOT / "csd" / "configuration_assurance"
DESCRIPTOR = CSD / "descriptor" / "service.sdl"
CONTROL_SCRIPT = CSD / "scripts" / "control.sh"

FAKE_CHECK = '''#!/usr/bin/env bash
python3 - "$@" <<'EOF'
import json, os, sys
with open(os.environ["FAKE_RECORD"], "a", encoding="utf-8") as record:
    record.write(json.dumps({"argv": sys.argv[1:], "env": dict(os.environ)}) + "\\n")
EOF
exit "${FAKE_CHECK_EXIT:-0}"
'''


def descriptor():
    """The parsed service descriptor."""
    return json.loads(DESCRIPTOR.read_text(encoding="utf-8"))


@unittest.skipUnless(DESCRIPTOR.is_file(), "Only applicable to a source checkout.")
class TestDescriptor(unittest.TestCase):
    """
    The service descriptor is consistent with itself, with control.sh, with the
    Makefile and with the files of the CSD.
    """

    def test_every_substitution_is_a_parameter(self):
        """
        Every ${...} the descriptor uses names a parameter it defines: a typo
        there is not an error in Cloudera Manager, but an empty value.
        """
        sdl = descriptor()
        role = sdl["roles"][0]
        defined = ({parameter["name"] for parameter in sdl["parameters"]}
                   | {parameter["name"] for parameter in role["parameters"]}
                   | {role["logging"]["configName"]})
        used = set(re.findall(r"\$\{([^}]+)\}", DESCRIPTOR.read_text(encoding="utf-8")))
        self.assertSetEqual(used - defined, set())

    def test_every_variable_handed_over_is_read(self):
        """
        Every environment variable the start runner sets is read by control.sh,
        so that no parameter is wired up to nothing.
        """
        script = CONTROL_SCRIPT.read_text(encoding="utf-8")
        handed_over = descriptor()["roles"][0]["startRunner"]["environmentVariables"]
        unread = [variable for variable in handed_over
                  if not re.search(r"\$\{%s[}:-]" % variable, script)]
        self.assertEqual(unread, [])

    def test_passwords_are_password_parameters(self):
        """
        The passwords are parameters of type password, which Cloudera Manager
        redacts in its API, its web interface and its exports.
        """
        types = {parameter["name"]: parameter["type"] for parameter in descriptor()["parameters"]}
        self.assertEqual(types["cloudera_manager_password"], "password")
        self.assertEqual(types["coguard_password"], "password")
        self.assertTrue(all(kind == "password" for name, kind in types.items()
                            if "password" in name))

    def test_defaults(self):
        """
        The service is unhealthy on High and Critical findings by default, the
        health of the service is the health of its role, and the parcel is
        required.
        """
        sdl = descriptor()
        defaults = {parameter["name"]: parameter.get("default") for parameter in sdl["parameters"]}
        self.assertEqual(defaults["minimum_fail_level"], 4)
        self.assertEqual(sdl["roles"][0]["healthAggregation"], {"type": "singleton"})
        self.assertEqual(sdl["parcel"]["requiredTags"], ["coguard"])
        self.assertNotIn("python_executable", defaults)

    def test_version_matches_the_makefile(self):
        """
        The jar is named after the version in the Makefile, and Cloudera Manager
        reads it from the descriptor; the two are the same.
        """
        makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn(f"CSD_VERSION := {descriptor()['version']}\n", makefile)

    def test_icons(self):
        """
        The icons the descriptor names exist; the PNG is 16x16, as Cloudera's
        own are.
        """
        sdl = descriptor()
        svg = CSD / sdl["svgIcon"]
        png = CSD / sdl["icon"]
        self.assertIn("<svg", svg.read_text(encoding="utf-8"))
        self.assertNotIn("<script", svg.read_text(encoding="utf-8"))
        header = png.read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", header[16:24]), (16, 16))


@unittest.skipUnless(CONTROL_SCRIPT.is_file() and shutil.which("bash"),
                     "Needs a source checkout and bash.")
class TestControlScript(unittest.TestCase):
    """
    The behaviour of control.sh.
    """

    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.record = self.directory / "record.jsonl"
        fake = self.directory / "fake-check"
        fake.write_text(FAKE_CHECK, encoding="utf-8")
        fake.chmod(0o755)
        self.environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "CLOUDERA_MANAGER_URL": "https://cm.example.com",
            "CHECK_EXECUTABLE": str(fake),
            "COGUARD_EXECUTABLE": "true",
            "WORK_DIRECTORY": str(self.directory),
            "LOG_DIR": str(self.directory),
            "CHECK_INTERVAL_SECONDS": "1",
            "ERROR_TOLERANCE": "2",
            "FAKE_RECORD": str(self.record),
            "CLOUDERA_MANAGER_PASSWORD": "cm-secret",
            "COGUARD_USER_NAME": "someone",
            "COGUARD_PASSWORD": "from-parameter",
            "ENVIRONMENT_FILE": "",
        }

    def run_control(self, **overrides):
        """Runs control.sh until it exits, and returns the completed process."""
        environment = dict(self.environment, **overrides)
        return subprocess.run(["bash", str(CONTROL_SCRIPT), "start"], env=environment,
                              capture_output=True, text=True, timeout=60, check=False)

    def calls(self):
        """What the stand-in for the check was started with, call by call."""
        if not self.record.exists():
            return []
        return [json.loads(line) for line in
                self.record.read_text(encoding="utf-8").splitlines()]

    def test_findings_end_the_role_with_1(self):
        """
        A check which ends with findings ends the role with 1, i.e. bad health,
        after the first check.
        """
        completed = self.run_control(FAKE_CHECK_EXIT="1")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Ending with a failure", completed.stdout)
        self.assertEqual(len(self.calls()), 1)

    def test_the_check_is_told_what_the_role_needs(self):
        """
        The check reports the outcome of the last scan as its exit code, writes
        the report into the log directory, uses the configured severity, and the
        first check after a start does not postpone its scan.
        """
        self.run_control(FAKE_CHECK_EXIT="1", MINIMUM_FAIL_LEVEL="5")
        argv = self.calls()[0]["argv"]
        self.assertIn("--exit-with-last-scan", argv)
        self.assertEqual(argv[argv.index("--report-file") + 1],
                         str(self.directory / "coguard-report.md"))
        self.assertEqual(argv[argv.index("--minimum-fail-level") + 1], "5")
        self.assertEqual(argv[argv.index("--minimum-scan-interval") + 1], "0")
        self.assertNotIn("--coguard-api-url", argv)
        self.assertNotIn("--report-url", argv)

    def test_optional_options(self):
        """
        The report link, a CoGuard instance of one's own, the rule set and the
        cluster are handed over when they are configured.
        """
        self.run_control(FAKE_CHECK_EXIT="1", COGUARD_ORGANIZATION="foobar",
                         COGUARD_CLUSTER_NAME="ozone_base_cluster",
                         REPORT_URL="https://portal.example.com",
                         COGUARD_API_URL="https://cg.example.com/server",
                         COGUARD_AUTH_URL="https://cg.example.com/auth",
                         RULESET="nist800-53", CLOUDERA_CLUSTER="ozone-base-cluster")
        argv = self.calls()[0]["argv"]
        expected = {
            "--report-url": "https://portal.example.com/orgs/foobar/ozone_base_cluster",
            "--coguard-cluster-name": "ozone_base_cluster",
            "--coguard-api-url": "https://cg.example.com/server",
            "--coguard-auth-url": "https://cg.example.com/auth",
            "--ruleset": "nist800-53",
            "--cloudera-cluster": "ozone-base-cluster",
        }
        for option, value in expected.items():
            self.assertEqual(argv[argv.index(option) + 1], value, option)

    def test_failed_checks_are_tolerated_up_to_the_limit(self):
        """
        A check which cannot be performed is retried, and the role ends with 2
        once the tolerance is used up: an unknown state is bad health too.
        """
        completed = self.run_control(FAKE_CHECK_EXIT="2")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(len(self.calls()), 2)
        self.assertIn("Giving up", completed.stdout)

    def test_a_stop_while_clean_is_an_orderly_end(self):
        """
        A clean role keeps checking, and a stop asked for by Cloudera Manager
        ends it with 0, not like a cluster with findings.
        """
        environment = dict(self.environment, FAKE_CHECK_EXIT="0")
        with subprocess.Popen(["bash", str(CONTROL_SCRIPT), "start"], env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as process:
            deadline = time.monotonic() + 30
            while len(self.calls()) < 2 and time.monotonic() < deadline:
                time.sleep(0.2)
            process.send_signal(signal.SIGTERM)
            stdout, _ = process.communicate(timeout=30)
        self.assertEqual(process.returncode, 0)
        self.assertIn("A stop was requested", stdout)
        self.assertGreaterEqual(len(self.calls()), 2)
        # Only the first check after a start skips the minimum scan interval.
        later = self.calls()[1]["argv"]
        self.assertEqual(later[later.index("--minimum-scan-interval") + 1], "900")

    def test_a_missing_check_command_is_an_error(self):
        """
        Without the parcel there is no check command, which is an error and not
        a clean cluster.
        """
        completed = self.run_control(CHECK_EXECUTABLE=str(self.directory / "missing"))
        self.assertEqual(completed.returncode, 2)
        self.assertIn("COGUARD parcel", completed.stdout)
        self.assertEqual(self.calls(), [])

    def test_credentials_from_the_parameters(self):
        """
        The credentials reach the check from the parameters, and an empty
        parameter is not handed on as an empty value.
        """
        self.run_control(FAKE_CHECK_EXIT="1", COGUARD_ORGANIZATION="")
        environment = self.calls()[0]["env"]
        self.assertEqual(environment["COGUARD_PASSWORD"], "from-parameter")
        self.assertEqual(environment["CLOUDERA_MANAGER_PASSWORD"], "cm-secret")
        self.assertNotIn("COGUARD_ORGANIZATION", environment)

    def test_credentials_file_is_read_verbatim_and_not_executed(self):
        """
        A credentials file overrides the parameters, every value is taken
        verbatim whatever characters it contains, quotes around a whole value are
        removed, and nothing in it is executed.
        """
        canary = self.directory / "pwned"
        credentials = self.directory / "cloudera.env"
        credentials.write_text(
            "# a comment\n"
            "\n"
            f"COGUARD_PASSWORD=a b;c$(touch {canary})`id`#!&|\n"
            "export COGUARD_USER_NAME='quoted user'\n"
            "COGUARD_ORGANIZATION=has=equals\n",
            encoding="utf-8"
        )
        credentials.chmod(0o400)
        self.run_control(FAKE_CHECK_EXIT="1", ENVIRONMENT_FILE=str(credentials))
        environment = self.calls()[0]["env"]
        self.assertEqual(environment["COGUARD_PASSWORD"],
                         f"a b;c$(touch {canary})`id`#!&|")
        self.assertEqual(environment["COGUARD_USER_NAME"], "quoted user")
        self.assertEqual(environment["COGUARD_ORGANIZATION"], "has=equals")
        self.assertFalse(canary.exists())

    def test_a_malformed_credentials_file_is_reported_without_its_content(self):
        """
        A line which is not KEY=value is an error, reported by its number only,
        since it may well be a password.
        """
        credentials = self.directory / "cloudera.env"
        credentials.write_text("COGUARD_USER_NAME=someone\nhunter2 is my password\n",
                               encoding="utf-8")
        completed = self.run_control(ENVIRONMENT_FILE=str(credentials))
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Line 2 of", completed.stdout)
        self.assertNotIn("hunter2", completed.stdout + completed.stderr)
        self.assertEqual(self.calls(), [])

    def test_missing_credentials_name_the_parameter(self):
        """
        Without a CoGuard account, or without the password of Cloudera Manager,
        the role does not start checking, and says which parameter to set.
        """
        completed = self.run_control(COGUARD_PASSWORD="")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("CoGuard Password", completed.stdout)
        completed = self.run_control(CLOUDERA_MANAGER_PASSWORD="")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("Cloudera Manager Password", completed.stdout)
        self.assertEqual(self.calls(), [])

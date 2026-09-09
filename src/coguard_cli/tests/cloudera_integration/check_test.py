"""
Tests for the `coguard-cloudera-check` entry point.
"""

import os
import pathlib
import tempfile
import unittest
import unittest.mock

from coguard_cli.cloudera_integration import EXIT_CLEAN, EXIT_ERROR
from coguard_cli.cloudera_integration import check

REVISION_CONTENT = ("User admin created a new revision. Message was: Setting "
                    "the value of ozone_security_enabled to true.")


def arguments(extra=None):
    """
    A helper producing the parsed arguments of a check.
    """
    return check.argument_parser().parse_args([
        "--cloudera-manager-url", "https://cm.example.com",
        "--cloudera-manager-user", "coguard"
    ] + (extra or []))


def credentials(**overrides):
    """
    A helper producing resolved Cloudera Manager credentials.
    """
    return {
        "url": "https://cm.example.com",
        "username": "coguard",
        "password": "secret",
        **overrides
    }


def event(code="EV_REVISION_CREATED",
          timestamp="2026-09-04T16:20:37.738Z",
          content=REVISION_CONTENT,
          cluster="ozone-base-cluster",
          service_name="ozone"):
    """
    A helper producing one event as Cloudera Manager reports it.
    """
    attributes = [{"name": "EVENTCODE", "values": [code]}]
    if cluster is not None:
        attributes.append({"name": "CLUSTER", "values": [cluster]})
    if service_name is not None:
        attributes.append(
            {"name": "SERVICE_DISPLAY_NAME", "values": [service_name]}
        )
    return {
        "id": f"event-{code}-{timestamp}",
        "content": content,
        "timeOccurred": timestamp,
        "category": "AUDIT_EVENT",
        "severity": "INFORMATIONAL",
        "attributes": attributes
    }


def api_with(events_by_code=None, unavailable=False):
    """
    A helper producing a Cloudera Manager client which answers the event queries
    of the check from a mapping of event code to events.
    """
    api = unittest.mock.MagicMock()

    def list_events(query, *_args, **_kwargs):
        if unavailable:
            return None
        return (events_by_code or {}).get(query.split("==", 1)[-1], [])

    api.list_events.side_effect = list_events
    return api


class TestClouderaCheck(unittest.TestCase):
    """
    The class for testing the Cloudera check entry point.
    """

    def test_parse_timestamp(self):
        """
        The timestamps of Cloudera Manager and of the state file are read, and an
        unusable one does not raise.
        """
        self.assertEqual(
            check.parse_timestamp("2026-09-04T16:20:37.738Z").isoformat(),
            "2026-09-04T16:20:37.738000+00:00"
        )
        # A timestamp without a time zone is read as UTC rather than rejected.
        self.assertEqual(
            check.parse_timestamp("2026-09-04T16:20:37").isoformat(),
            "2026-09-04T16:20:37+00:00"
        )
        self.assertIsNone(check.parse_timestamp(None))
        self.assertIsNone(check.parse_timestamp(""))
        self.assertIsNone(check.parse_timestamp("the day before yesterday"))

    def test_is_newer(self):
        """
        Timestamps are compared, and anything which cannot be compared counts as
        newer, so that a scan is run rather than a change skipped.
        """
        self.assertTrue(check.is_newer("2026-09-04T16:20:38.000Z",
                                       "2026-09-04T16:20:37.738Z"))
        self.assertFalse(check.is_newer("2026-09-04T16:20:37.738Z",
                                        "2026-09-04T16:20:37.738Z"))
        self.assertFalse(check.is_newer("2026-09-01T00:00:00.000Z",
                                        "2026-09-04T16:20:37.738Z"))
        self.assertTrue(check.is_newer("2026-09-01T00:00:00.000Z", None))
        self.assertTrue(check.is_newer(None, "2026-09-04T16:20:37.738Z"))
        self.assertTrue(check.is_newer("no timestamp",
                                       "2026-09-04T16:20:37.738Z"))

    def test_seconds_since(self):
        """
        A timestamp of the state file is read, and an unusable one does not raise.
        """
        self.assertIsNone(check.seconds_since(None))
        self.assertIsNone(check.seconds_since("the day before yesterday"))
        self.assertLess(check.seconds_since(check.now()), 5)

    def test_read_and_write_state(self):
        """
        The state survives a round trip through the state file.
        """
        temp_dir = tempfile.mkdtemp(prefix="coguard-cloudera-check-test")
        state_file = os.path.join(temp_dir, "nested", "state.json")
        try:
            check.write_state(state_file, {"cluster": "ozone-base-cluster"})
            self.assertEqual(
                check.read_state(state_file),
                {"cluster": "ozone-base-cluster"}
            )
        finally:
            os.remove(state_file)
            os.rmdir(os.path.dirname(state_file))
            os.rmdir(temp_dir)

    def test_read_state_without_a_state_file(self):
        """
        A state file which is not there yet results in an empty state.
        """
        self.assertEqual(
            check.read_state("/tmp/a-state-file-which-does-not-exist.json"),
            {}
        )

    def test_read_state_which_cannot_be_read(self):
        """
        A state file which cannot be read results in an empty state, i.e. in a
        scan, rather than in a failure.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.pathlib.Path.read_text',
                side_effect=OSError("permission denied")
        ):
            self.assertEqual(check.read_state("/etc/shadow-state.json"), {})

    def test_read_state_which_is_not_json(self):
        """
        A state file which is not JSON results in an empty state.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.pathlib.Path.read_text',
                new_callable=lambda: unittest.mock.MagicMock(
                    return_value="not json"
                )
        ):
            self.assertEqual(check.read_state("state.json"), {})

    def test_write_state_which_cannot_be_written(self):
        """
        A state file which cannot be written is reported, but does not fail the
        check.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.pathlib.Path.write_text',
                side_effect=OSError("read-only file system")
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.pathlib.Path.mkdir'
        ):
            check.write_state("/proc/state.json", {})

    def test_event_cluster(self):
        """
        The cluster of an event is read from either of the two attributes which
        name it, and an event which is not about one cluster has none.
        """
        self.assertEqual(check.event_cluster(event()), "ozone-base-cluster")
        self.assertEqual(
            check.event_cluster({
                "attributes": [{"name": "CLUSTER_DISPLAY_NAME",
                                "values": ["ozone-base-cluster"]}]
            }),
            "ozone-base-cluster"
        )
        self.assertIsNone(check.event_cluster(event(cluster=None)))

    def test_describe_event(self):
        """
        An event is stated with the service it belongs to, and an event without a
        description falls back to its code.
        """
        self.assertEqual(
            check.describe_event(event()),
            f"ozone: {REVISION_CONTENT}"
        )
        self.assertEqual(
            check.describe_event(event(service_name=None)),
            REVISION_CONTENT
        )
        self.assertEqual(
            check.describe_event(event(content="", service_name=None)),
            "EV_REVISION_CREATED"
        )
        self.assertEqual(
            check.describe_event({}),
            "an event without a description"
        )

    def test_describe_events_names_only_the_first_ones(self):
        """
        The reason for a scan names a bounded number of events, and says how many
        there were beyond that.
        """
        described = check.describe_events([
            event(timestamp=f"2026-09-04T16:20:{second:02d}.000Z")
            for second in range(check.MAXIMUM_DESCRIBED_EVENTS + 2)
        ])
        self.assertEqual(described.count(REVISION_CONTENT),
                         check.MAXIMUM_DESCRIBED_EVENTS)
        self.assertIn("and 2 further event(s)", described)

    def test_poll_events_returns_the_new_events_of_this_cluster(self):
        """
        Only the events which are newer than the watermark and belong to the
        cluster being checked are returned, and the watermark moves to the newest
        event which exists.
        """
        api = api_with({
            "EV_REVISION_CREATED": [
                event(timestamp="2026-09-04T16:20:39.000Z"),
                event(timestamp="2026-09-04T16:20:38.000Z",
                      cluster="another-cluster"),
                event(timestamp="2026-09-04T16:20:37.000Z"),
                event(timestamp="2026-09-04T16:20:36.000Z")
            ],
            "EV_PARCEL_ACTIVATE": [
                # A parcel is not about a single cluster, and is relevant to the
                # one being checked.
                event(code="EV_PARCEL_ACTIVATE",
                      timestamp="2026-09-04T16:20:38.500Z",
                      cluster=None,
                      service_name=None)
            ]
        })
        result = check.poll_events(
            api,
            "ozone-base-cluster",
            list(check.WATCHED_EVENT_CODES),
            "2026-09-04T16:20:37.000Z"
        )
        self.assertEqual(
            [item["timeOccurred"] for item in result["events"]],
            ["2026-09-04T16:20:39.000Z", "2026-09-04T16:20:38.500Z"]
        )
        self.assertEqual(result["newest"], "2026-09-04T16:20:39.000Z")
        self.assertFalse(result["truncated"])
        # One request per watched event code, and the code is what is filtered on.
        self.assertEqual(api.list_events.call_count,
                         len(check.WATCHED_EVENT_CODES))
        self.assertEqual(
            api.list_events.call_args_list[0].args[0],
            "attributes.EVENTCODE==EV_REVISION_CREATED"
        )

    def test_poll_events_without_new_events(self):
        """
        A cluster whose newest event is the watermark itself has not changed, and
        the watermark stays where it is.
        """
        result = check.poll_events(
            api_with({"EV_REVISION_CREATED": [event()]}),
            "ozone-base-cluster",
            ["EV_REVISION_CREATED"],
            "2026-09-04T16:20:37.738Z"
        )
        self.assertEqual(result["events"], [])
        self.assertEqual(result["newest"], "2026-09-04T16:20:37.738Z")
        self.assertFalse(result["truncated"])

    def test_poll_events_without_a_watermark(self):
        """
        Without a watermark every event is new, and the watermark is set to the
        newest one.
        """
        result = check.poll_events(
            api_with({
                "EV_REVISION_CREATED": [
                    event(timestamp="2026-09-04T16:20:37.738Z"),
                    event(timestamp="2026-09-04T15:00:00.000Z")
                ]
            }),
            "ozone-base-cluster",
            ["EV_REVISION_CREATED"],
            None
        )
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["newest"], "2026-09-04T16:20:37.738Z")

    def test_poll_events_notices_a_full_page(self):
        """
        A full page of events which does not reach back to the watermark means
        that events were not returned, which is not the same as no change.
        """
        page = [
            event(timestamp=f"2026-09-04T16:{minute:02d}:00.000Z")
            for minute in range(60 - check.DEFAULT_EVENT_PAGE_SIZE, 60)
        ]
        result = check.poll_events(
            api_with({"EV_REVISION_CREATED": page}),
            "ozone-base-cluster",
            ["EV_REVISION_CREATED"],
            "2026-09-04T15:00:00.000Z"
        )
        self.assertTrue(result["truncated"])
        # The same page, but the watermark is younger than its oldest entry, so
        # nothing is missing.
        result = check.poll_events(
            api_with({"EV_REVISION_CREATED": page}),
            "ozone-base-cluster",
            ["EV_REVISION_CREATED"],
            "2026-09-04T16:30:00.000Z"
        )
        self.assertFalse(result["truncated"])

    def test_poll_events_without_an_answer(self):
        """
        An events resource which does not answer is a failure to look, not a
        cluster which did not change.
        """
        self.assertIsNone(check.poll_events(
            api_with(unavailable=True),
            "ozone-base-cluster",
            ["EV_REVISION_CREATED"],
            None
        ))

    def test_scan_reason(self):
        """
        A scan is due for a cluster whose event feed has not been read, for one
        which reported an event, for one whose events could not all be seen, and
        for one whose last scan is too old.
        """
        unchanged = {"events": [], "newest": "2026-09-04T16:20:37.738Z",
                     "truncated": False}
        self.assertIn(
            "has not been read before",
            check.scan_reason({}, unchanged, 3600)
        )
        state = {"lastEventAt": "2026-09-04T16:20:37.738Z",
                 "lastScanAt": check.now()}
        self.assertIn(
            REVISION_CONTENT,
            check.scan_reason(state, {**unchanged, "events": [event()]}, 3600)
        )
        self.assertIn(
            "full page of events",
            check.scan_reason(state, {**unchanged, "truncated": True}, 3600)
        )
        self.assertIn(
            "no scan has been recorded",
            check.scan_reason(
                {"lastEventAt": "2026-09-04T16:20:37.738Z"}, unchanged, 3600
            )
        )
        self.assertIn(
            "due every 3600 seconds",
            check.scan_reason(
                {
                    "lastEventAt": "2026-09-04T16:20:37.738Z",
                    "lastScanAt": "2020-01-01T00:00:00+00:00"
                },
                unchanged,
                3600
            )
        )

    def test_scan_reason_of_an_unchanged_cluster(self):
        """
        An unchanged cluster whose last scan is recent enough is not scanned, and
        a maximum scan age of zero switches the periodic scan off.
        """
        unchanged = {"events": [], "newest": "2026-09-04T16:20:37.738Z",
                     "truncated": False}
        self.assertIsNone(check.scan_reason(
            {"lastEventAt": "2026-09-04T16:20:37.738Z",
             "lastScanAt": check.now()},
            unchanged,
            3600
        ))
        self.assertIsNone(check.scan_reason(
            {"lastEventAt": "2026-09-04T16:20:37.738Z",
             "lastScanAt": "2020-01-01T00:00:00+00:00"},
            unchanged,
            0
        ))

    def test_build_cli_arguments(self):
        """
        The command line carries the options of the CLI before the sub-command
        and the connection parameters after it, and no password.
        """
        built = check.build_cli_arguments(
            arguments([
                "--minimum-fail-level", "3",
                "--ruleset", "nist800-53",
                "--coguard-api-url", "https://portal.example.com/server",
                "--coguard-auth-url", "https://auth.example.com"
            ]),
            credentials(ca_cert="/etc/ssl/cm.pem", verify_tls=False),
            "ozone-base-cluster"
        )
        self.assertEqual(built[0], "coguard")
        self.assertEqual(built[built.index("cloud") + 1], "cloudera")
        for option in ("--minimum-fail-level", "--ruleset", "--coguard-api-url",
                       "--coguard-auth-url", "--logging-level"):
            self.assertLess(built.index(option), built.index("cloud"))
        for option in ("--cloudera-manager-url", "--cloudera-manager-user",
                       "--cloudera-manager-ca-cert", "--cloudera-cluster"):
            self.assertGreater(built.index(option), built.index("cloud"))
        self.assertIn("--cloudera-manager-no-verify-tls", built)
        self.assertEqual(
            built[built.index("--cloudera-cluster") + 1],
            "ozone-base-cluster"
        )
        self.assertTrue(all("secret" not in entry for entry in built))
        self.assertTrue(all("password" not in entry for entry in built))

    def test_build_cli_arguments_minimal(self):
        """
        Options which were not provided do not show up on the command line, so
        that the defaults of the CoGuard CLI apply.
        """
        built = check.build_cli_arguments(
            arguments(),
            credentials(),
            "ozone-base-cluster"
        )
        self.assertNotIn("--minimum-fail-level", built)
        self.assertNotIn("--ruleset", built)
        self.assertNotIn("--cloudera-manager-ca-cert", built)
        self.assertNotIn("--cloudera-manager-no-verify-tls", built)

    def test_run_scan(self):
        """
        The exit code of the CoGuard CLI is the outcome of the scan, and the
        password reaches it through the environment.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.shutil.which',
                new_callable=lambda: unittest.mock.MagicMock(
                    return_value="/usr/bin/coguard"
                )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.subprocess.run',
            new_callable=lambda: unittest.mock.MagicMock(
                return_value=unittest.mock.MagicMock(returncode=1)
            )
        ) as subprocess_run:
            self.assertEqual(
                check.run_scan(
                    ["coguard", "cloud", "cloudera"],
                    {"CLOUDERA_MANAGER_PASSWORD": "secret"}
                ),
                1
            )
        environment = subprocess_run.call_args.kwargs["env"]
        self.assertEqual(environment["CLOUDERA_MANAGER_PASSWORD"], "secret")
        self.assertIn("PATH", environment)

    def test_run_scan_without_the_cli(self):
        """
        A CoGuard CLI which is not on the path is reported, and is not the same
        outcome as a scan which found something.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.shutil.which',
                new_callable=lambda: unittest.mock.MagicMock(return_value=None)
        ):
            self.assertIsNone(check.run_scan(["coguard"]))

    def test_perform_check_of_a_changed_cluster(self):
        """
        A cluster which reported a configuration change is scanned, the exit code
        of the scan is the exit code of the check, and the position in the event
        feed moves on.
        """
        state = {
            "cluster": "ozone-base-cluster",
            "lastEventAt": "2026-09-04T16:00:00.000Z",
            "lastScanAt": "2020-01-01T00:00:00+00:00"
        }
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.run_scan',
                new_callable=lambda: unittest.mock.MagicMock(return_value=1)
        ) as run_scan:
            new_state, exit_code = check.perform_check(
                api_with({"EV_REVISION_CREATED": [event()]}),
                "ozone-base-cluster",
                arguments(),
                credentials(),
                state
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(new_state["lastScanExitCode"], 1)
        self.assertIn("ozone_security_enabled", new_state["lastScanReason"])
        self.assertEqual(new_state["lastEventAt"], "2026-09-04T16:20:37.738Z")
        self.assertEqual(
            run_scan.call_args.args[1],
            {"CLOUDERA_MANAGER_PASSWORD": "secret"}
        )

    def test_perform_check_of_an_unchanged_cluster(self):
        """
        A cluster which did not change is not scanned.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.run_scan'
        ) as run_scan:
            new_state, exit_code = check.perform_check(
                api_with({"EV_REVISION_CREATED": [event()]}),
                "ozone-base-cluster",
                arguments(),
                credentials(),
                {
                    "lastEventAt": "2026-09-04T16:20:37.738Z",
                    "lastScanAt": check.now()
                }
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        run_scan.assert_not_called()
        self.assertIn("lastCheckedAt", new_state)
        self.assertNotIn("lastScanExitCode", new_state)

    def test_perform_check_of_a_cluster_which_was_never_checked(self):
        """
        The first check of a cluster scans it, whatever its event feed says, and
        remembers where the feed stood.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.run_scan',
                new_callable=lambda: unittest.mock.MagicMock(return_value=0)
        ) as run_scan:
            new_state, exit_code = check.perform_check(
                api_with({"EV_REVISION_CREATED": [event()]}),
                "ozone-base-cluster",
                arguments(),
                credentials(),
                {}
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        run_scan.assert_called_once()
        self.assertIn("has not been read before", new_state["lastScanReason"])
        self.assertEqual(new_state["lastEventAt"], "2026-09-04T16:20:37.738Z")

    def test_perform_check_postpones_a_scan(self):
        """
        A change shortly after a scan is postponed, and stays a change, so that a
        rolling restart does not result in a scan per service.
        """
        state = {
            "lastEventAt": "2026-09-04T16:00:00.000Z",
            "lastScanAt": check.now()
        }
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.run_scan'
        ) as run_scan:
            new_state, exit_code = check.perform_check(
                api_with({"EV_REVISION_CREATED": [event()]}),
                "ozone-base-cluster",
                arguments(),
                credentials(),
                state
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        run_scan.assert_not_called()
        self.assertEqual(new_state["lastEventAt"], "2026-09-04T16:00:00.000Z")

    def test_perform_check_without_an_answer_from_cloudera_manager(self):
        """
        A Cloudera Manager whose events cannot be read is an error, and leaves the
        remembered position in the event feed alone.
        """
        state = {"lastEventAt": "2026-09-04T16:00:00.000Z"}
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.run_scan'
        ) as run_scan:
            new_state, exit_code = check.perform_check(
                api_with(unavailable=True),
                "ozone-base-cluster",
                arguments(),
                credentials(),
                state
            )
        self.assertEqual(exit_code, EXIT_ERROR)
        run_scan.assert_not_called()
        self.assertEqual(new_state["lastEventAt"], state["lastEventAt"])

    def test_perform_check_with_a_scan_which_could_not_be_run(self):
        """
        A scan which could not be run at all leaves the change pending, rather
        than recording the cluster as scanned.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.run_scan',
                new_callable=lambda: unittest.mock.MagicMock(return_value=None)
        ):
            new_state, exit_code = check.perform_check(
                api_with({"EV_REVISION_CREATED": [event()]}),
                "ozone-base-cluster",
                arguments(),
                credentials(),
                {}
            )
        self.assertEqual(exit_code, EXIT_ERROR)
        self.assertNotIn("lastEventAt", new_state)
        self.assertNotIn("lastScanAt", new_state)

    def test_perform_check_with_the_event_codes_of_the_command_line(self):
        """
        The event codes of the command line replace the ones this check watches
        by default, so that a Cloudera Manager which reports a change through
        another code can be followed without a new release.
        """
        api = api_with({"EV_SOMETHING_ELSE": [event(code="EV_SOMETHING_ELSE")]})
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.run_scan',
                new_callable=lambda: unittest.mock.MagicMock(return_value=0)
        ):
            check.perform_check(
                api,
                "ozone-base-cluster",
                arguments(["--event-code", "EV_SOMETHING_ELSE"]),
                credentials(),
                {"lastEventAt": "2026-09-04T16:00:00.000Z",
                 "lastScanAt": "2020-01-01T00:00:00+00:00"}
            )
        self.assertEqual(
            [call.args[0] for call in api.list_events.call_args_list],
            ["attributes.EVENTCODE==EV_SOMETHING_ELSE"]
        )

    def test_main(self):
        """
        The entry point performs one check, stores the state and returns the exit
        code of the check.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.resolve_credentials',
                new_callable=lambda: unittest.mock.MagicMock(
                    return_value=credentials()
                )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.connect'
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.determine_cluster_name',
            new_callable=lambda: unittest.mock.MagicMock(
                return_value="ozone-base-cluster"
            )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.read_state',
            new_callable=lambda: unittest.mock.MagicMock(return_value={})
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.write_state'
        ) as write_state, unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.perform_check',
            new_callable=lambda: unittest.mock.MagicMock(
                return_value=({"cluster": "ozone-base-cluster"}, 1)
            )
        ):
            self.assertEqual(
                check.main([
                    "--cloudera-manager-url", "https://cm.example.com",
                    "--cloudera-manager-user", "coguard"
                ]),
                1
            )
        write_state.assert_called_once()

    def test_main_starts_over_for_another_cluster(self):
        """
        A state file which describes another cluster is not compared against.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.resolve_credentials',
                new_callable=lambda: unittest.mock.MagicMock(
                    return_value=credentials()
                )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.connect'
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.determine_cluster_name',
            new_callable=lambda: unittest.mock.MagicMock(
                return_value="ozone-base-cluster"
            )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.read_state',
            new_callable=lambda: unittest.mock.MagicMock(
                return_value={"cluster": "another-cluster",
                              "lastEventAt": "2026-09-04T16:00:00.000Z"}
            )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.write_state'
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.perform_check',
            new_callable=lambda: unittest.mock.MagicMock(
                return_value=({}, EXIT_CLEAN)
            )
        ) as perform_check:
            self.assertEqual(check.main([]), EXIT_CLEAN)
        self.assertEqual(perform_check.call_args.args[4], {})

    def test_main_without_credentials(self):
        """
        A connection which cannot be described is an error.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.resolve_credentials',
                new_callable=lambda: unittest.mock.MagicMock(return_value=None)
        ):
            self.assertEqual(check.main([]), EXIT_ERROR)

    def test_main_without_a_connection(self):
        """
        A Cloudera Manager which cannot be reached is an error.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.resolve_credentials',
                new_callable=lambda: unittest.mock.MagicMock(
                    return_value=credentials()
                )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.connect',
            new_callable=lambda: unittest.mock.MagicMock(return_value=None)
        ):
            self.assertEqual(check.main([]), EXIT_ERROR)

    def test_main_without_a_cluster(self):
        """
        A Cloudera Manager whose cluster cannot be determined is an error.
        """
        with unittest.mock.patch(
                'coguard_cli.cloudera_integration.check.resolve_credentials',
                new_callable=lambda: unittest.mock.MagicMock(
                    return_value=credentials()
                )
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.connect'
        ), unittest.mock.patch(
            'coguard_cli.cloudera_integration.check.determine_cluster_name',
            new_callable=lambda: unittest.mock.MagicMock(return_value=None)
        ):
            self.assertEqual(check.main([]), EXIT_ERROR)

    def test_the_default_state_file_is_in_the_configuration_directory(self):
        """
        The state is kept next to the CoGuard configuration of the user running
        the check.
        """
        self.assertEqual(
            pathlib.Path(check.DEFAULT_STATE_FILE).parent.name,
            "coguard-cli"
        )

    def test_the_configuration_change_event_is_watched(self):
        """
        The event which names a changed configuration parameter is the reason this
        check exists, and the moment a change takes effect is watched as well.
        """
        self.assertIn("EV_REVISION_CREATED", check.WATCHED_EVENT_CODES)
        self.assertIn("EV_SERVICE_RESTARTED", check.WATCHED_EVENT_CODES)

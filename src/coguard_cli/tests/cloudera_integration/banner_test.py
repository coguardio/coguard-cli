"""
Tests for the `coguard-cloudera-banner` entry point.
"""

import json
import pathlib
import tempfile
import unittest
import unittest.mock

import requests

from coguard_cli.cloudera_integration import EXIT_CLEAN, EXIT_ERROR
from coguard_cli.cloudera_integration import banner


def arguments(extra=None):
    """
    A helper producing the parsed arguments of a banner run.
    """
    return banner.argument_parser().parse_args([
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


def finding(severity=4, name="ozone_grpc_tls_enabled", service="ozone_manager"):
    """
    A helper producing one failed check as a result JSON reports it.
    """
    return {
        "rule": {
            "name": name,
            "humanReadableName": name.replace("_", " "),
            "severity": severity,
            "documentation": {
                "documentation": "",
                "remediation": "",
                "sources": []
            }
        },
        "fromLine": 0,
        "toLine": 1,
        "service": service,
        "config_file": {
            "fileName": "ozone-site.xml",
            "subPath": ".",
            "configFileType": "xml"
        }
    }


def result_file(directory, findings):
    """
    A helper writing a result JSON and returning its path.
    """
    path = pathlib.Path(directory) / "result.json"
    with path.open('w', encoding='utf-8') as result_stream:
        json.dump({"failed": findings}, result_stream)
    return str(path)


def response_with(payload=None, text="v58", ok=True, status_code=200):
    """
    A helper producing a Cloudera Manager response.
    """
    response = unittest.mock.MagicMock()
    response.ok = ok
    response.status_code = status_code
    response.text = text
    if payload is None:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = payload
    return response


def api_with(config_items):
    """
    A helper producing a banner client whose configuration read answers with the
    given items and whose write records what it was called with.
    """
    api = banner.ClouderaManagerBannerApi(
        base_url="https://cm.example.com",
        username="coguard",
        password="secret"
    )
    api._api_version = "v58"  # pylint: disable=protected-access
    api._session = unittest.mock.MagicMock()  # pylint: disable=protected-access
    # pylint: disable=protected-access
    api._session.get.return_value = response_with({"items": config_items})
    api._session.put.return_value = response_with({})
    return api


class SeverityBucketTest(unittest.TestCase):
    """
    The naming of severities, which follows what the CLI prints.
    """

    def test_buckets_match_the_cli_output(self):
        """
        Everything above 3 is High, 3 is Medium, everything below is Low.
        """
        self.assertEqual(banner.severity_bucket(5), "High")
        self.assertEqual(banner.severity_bucket(4), "High")
        self.assertEqual(banner.severity_bucket(3), "Medium")
        self.assertEqual(banner.severity_bucket(2), "Low")
        self.assertEqual(banner.severity_bucket(0), "Low")


class ReadResultTest(unittest.TestCase):
    """
    Reading the result JSON of a scan.
    """

    def test_a_result_is_read(self):
        """
        The happy path.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            self.assertEqual(len(banner.read_result(path)["failed"]), 1)

    def test_a_missing_file_is_reported(self):
        """
        A scan which has not run yet is not an exception.
        """
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(
                banner.read_result(str(pathlib.Path(directory) / "nope.json"))
            )

    def test_a_broken_file_is_reported(self):
        """
        A truncated result JSON is not an exception either.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "result.json"
            path.write_text("{not json", encoding='utf-8')
            self.assertIsNone(banner.read_result(str(path)))

    def test_a_result_which_is_not_an_object_is_reported(self):
        """
        A JSON document which is not a result is refused.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "result.json"
            path.write_text("[]", encoding='utf-8')
            self.assertIsNone(banner.read_result(str(path)))


class FailedFindingsTest(unittest.TestCase):
    """
    Selecting the findings which are shown.
    """

    def test_the_severity_is_a_lower_bound(self):
        """
        Only findings at or above the minimum severity are counted.
        """
        findings = [finding(severity=2), finding(severity=4)]
        self.assertEqual(len(banner.failed_findings({"failed": findings}, 1)), 2)
        self.assertEqual(len(banner.failed_findings({"failed": findings}, 4)), 1)
        self.assertEqual(len(banner.failed_findings({"failed": findings}, 5)), 0)

    def test_entries_which_are_not_findings_are_ignored(self):
        """
        A result without a rule, or with a rule which is not an object, does not
        break the count.
        """
        result = {"failed": [finding(), {"service": "x"}, "nonsense",
                             {"rule": "nonsense"}]}
        self.assertEqual(len(banner.failed_findings(result, 1)), 1)

    def test_a_result_without_failures_is_empty(self):
        """
        A clean scan has nothing to show.
        """
        self.assertEqual(banner.failed_findings({}, 1), [])
        self.assertEqual(banner.failed_findings({"failed": None}, 1), [])


class SummarizeTest(unittest.TestCase):
    """
    Counting the findings.
    """

    def test_buckets_are_worst_first_and_only_the_ones_which_occur(self):
        """
        A result with no medium findings does not mention medium ones.
        """
        buckets, _ = banner.summarize([finding(severity=5), finding(severity=4),
                                       finding(severity=2)])
        self.assertEqual(buckets, [("High", 2), ("Low", 1)])

    def test_services_are_ordered_by_their_worst_finding(self):
        """
        A service with one high finding comes before a service with many low
        ones, and equal severity is broken by the count.
        """
        _, services = banner.summarize([
            finding(severity=2, service="low_many"),
            finding(severity=2, service="low_many"),
            finding(severity=5, service="high_one"),
            finding(severity=2, service="low_one"),
        ])
        self.assertEqual(services,
                         [("high_one", 1), ("low_many", 2), ("low_one", 1)])

    def test_a_finding_without_a_service_is_attributed_to_the_cluster(self):
        """
        A finding of a machine rather than a cluster service still counts.
        """
        _, services = banner.summarize([{"rule": {"severity": 3}}])
        self.assertEqual(services, [("the cluster", 1)])


class RenderBlockTest(unittest.TestCase):
    """
    The text which is put into the banner.
    """

    def test_a_clean_result_says_so(self):
        """
        A scan without findings is worth showing, since it is the difference
        between a clean cluster and a scan which never ran.
        """
        block = banner.render_block([], "ozone-base-cluster", None, 5)
        self.assertIn("no findings", block)
        self.assertIn("ozone-base-cluster", block)
        self.assertTrue(block.startswith(banner.BLOCK_MARKER))

    def test_the_block_is_text_and_not_markup(self):
        """
        Cloudera Manager escapes the value of the parameter, so markup in it is
        shown to the user as markup.
        """
        block = banner.render_block(
            [finding(severity=5, service="knox_gateway")],
            "ozone-base-cluster",
            "https://portal.coguard.io",
            5
        )
        self.assertNotIn("<", block)
        self.assertNotIn(">", block)
        self.assertEqual(block, block.strip())
        self.assertNotIn("\n", block)

    def test_findings_are_counted_and_the_services_named(self):
        """
        The counts and the affected services are what the banner is for.
        """
        block = banner.render_block(
            [finding(severity=5, service="knox_gateway"),
             finding(severity=3, service="ozone_manager")],
            "ozone-base-cluster",
            None,
            5
        )
        self.assertIn("2 configuration findings", block)
        self.assertIn("1 High, 1 Medium", block)
        self.assertIn("knox_gateway (1)", block)
        self.assertIn("ozone_manager (1)", block)

    def test_a_single_finding_is_not_pluralized(self):
        """
        One finding is a finding.
        """
        block = banner.render_block([finding()], None, None, 5)
        self.assertIn("1 configuration finding (", block)

    def test_the_number_of_named_services_is_capped(self):
        """
        The banner is a header, so the rest of the services is a count.
        """
        block = banner.render_block(
            [finding(service=f"service_{index}") for index in range(4)],
            None,
            None,
            2
        )
        self.assertIn("and 2 further services", block)
        self.assertNotIn("service_3", block)

    def test_one_remaining_service_is_not_pluralized(self):
        """
        The same, for the boundary of the cap.
        """
        block = banner.render_block(
            [finding(service=f"service_{index}") for index in range(3)],
            None,
            None,
            2
        )
        self.assertIn("and 1 further service.", block)

    def test_a_cluster_name_is_optional(self):
        """
        A Cloudera Manager whose cluster could not be determined still gets a
        banner.
        """
        self.assertNotIn(" of ", banner.render_block([finding()], None, None, 5))

    def test_values_taken_from_the_result_cannot_become_markup(self):
        """
        A service name is data, and a version of Cloudera Manager which renders
        the banner instead of escaping it would render whatever is in it.
        """
        block = banner.render_block(
            [finding(service="<script>alert(1)</script>")],
            "<cluster>",
            None,
            5
        )
        self.assertNotIn("<", block)
        self.assertNotIn(">", block)
        self.assertIn("scriptalert(1)/script", block)
        self.assertIn("cluster", block)

    def test_a_value_of_more_than_one_line_stays_on_one(self):
        """
        The banner is a header, and a newline in it would break the header of
        every page.
        """
        block = banner.render_block([finding(service="knox\ngateway")], None,
                                    None, 5)
        self.assertIn("knox gateway", block)
        self.assertNotIn("\n", block)

    def test_the_report_url_is_shown_as_an_address(self):
        """
        The address cannot be a link in a banner which is text, so it is written
        out for copying.
        """
        block = banner.render_block(
            [finding()],
            None,
            'https://portal.coguard.io/x?a=1&b=2',
            5
        )
        self.assertIn("Full report: https://portal.coguard.io/x?a=1&b=2", block)

    def test_without_a_report_url_no_address_is_shown(self):
        """
        The address is only shown when there is something to point to.
        """
        self.assertNotIn("Full report", banner.render_block([finding()], None,
                                                            None, 5))


class ReplaceBlockTest(unittest.TestCase):
    """
    Sharing the banner with whoever else writes to it.
    """

    def test_an_empty_banner_becomes_the_block(self):
        """
        The common case of a cluster with no banner.
        """
        self.assertEqual(banner.replace_block(None, "CoGuard: x"), "CoGuard: x")
        self.assertEqual(banner.replace_block("", "CoGuard: x"), "CoGuard: x")

    def test_text_of_somebody_else_is_kept(self):
        """
        A banner a customer put there is not ours to remove.
        """
        self.assertEqual(banner.replace_block("Production.", "CoGuard: x"),
                         "Production. | CoGuard: x")

    def test_an_earlier_block_is_replaced_and_not_appended_to(self):
        """
        Running the command twice leaves one block, not two.
        """
        first = banner.replace_block("Production.", "CoGuard: old")
        second = banner.replace_block(first, "CoGuard: new")
        self.assertEqual(second, "Production. | CoGuard: new")
        self.assertEqual(second.count(banner.BLOCK_MARKER), 1)

    def test_an_empty_block_removes_the_region(self):
        """
        What `--clear` does. The separator goes with it, so that the banner of
        the customer is left as it was.
        """
        self.assertEqual(
            banner.replace_block("Production. | CoGuard: old", ""),
            "Production."
        )
        self.assertEqual(banner.replace_block("CoGuard: old", ""), "")

    def test_a_block_written_as_html_by_an_earlier_version_is_removed(self):
        """
        The first version of this command wrapped its text in markup between
        HTML comments. Cloudera Manager escapes the value, so such a banner is
        visible markup, and it has to be recognised and replaced rather than
        treated as text of the customer.
        """
        current = (f"Production. {banner.LEGACY_BLOCK_START}"
                   f'<span style="color:#b42318;">CoGuard: 5 findings.</span>'
                   f"{banner.LEGACY_BLOCK_END}")
        result = banner.replace_block(current, "CoGuard: new")
        self.assertEqual(result, "Production. | CoGuard: new")

    def test_an_unterminated_html_block_is_ours_and_is_dropped(self):
        """
        An interrupted run of that version left a start delimiter without an end.
        What follows it was written by us, so it is replaced rather than kept.
        """
        current = f"before {banner.LEGACY_BLOCK_START}<span>partial"
        once = banner.replace_block(current, "CoGuard: new")
        self.assertEqual(once, "before | CoGuard: new")
        self.assertEqual(banner.replace_block(once, "CoGuard: new"), once)


class ClouderaManagerBannerApiTest(unittest.TestCase):
    """
    The one client of this integration which writes.
    """

    def test_the_configuration_is_read_as_a_mapping(self):
        """
        A parameter which is not set is `None`, and not absent.
        """
        api = api_with([{"name": "CUSTOM_BANNER_HTML", "value": None},
                        {"name": "OTHER", "value": "x"},
                        {"value": "no name"},
                        "nonsense"])
        self.assertEqual(api.get_cm_config(),
                         {"CUSTOM_BANNER_HTML": None, "OTHER": "x"})

    def test_a_configuration_which_cannot_be_read_is_reported(self):
        """
        A Cloudera Manager which refuses the read.
        """
        api = api_with([])
        # pylint: disable=protected-access
        api._session.get.side_effect = requests.RequestException("nope")
        self.assertIsNone(api.get_cm_config())

    def test_a_configuration_which_cannot_be_decoded_is_reported(self):
        """
        A reverse proxy answering with an error page.
        """
        api = api_with([])
        # pylint: disable=protected-access
        api._session.get.return_value = response_with(None)
        self.assertIsNone(api.get_cm_config())

    def test_a_write_names_only_the_parameters_it_changes(self):
        """
        A partial update, so that the other parameters of the resource are not
        part of the request at all.
        """
        api = api_with([])
        self.assertTrue(api.put_cm_config({"CUSTOM_BANNER_HTML": "value"}))
        # pylint: disable=protected-access
        _, keyword_arguments = api._session.put.call_args
        self.assertEqual(
            keyword_arguments["json"],
            {"items": [{"name": "CUSTOM_BANNER_HTML", "value": "value"}]}
        )

    def test_several_parameters_are_one_request(self):
        """
        One request is one configuration revision, so the banner and the header
        colour are not two changes in the event feed of the cluster.
        """
        api = api_with([])
        self.assertTrue(api.put_cm_config({"CUSTOM_BANNER_HTML": "value",
                                           "CUSTOM_HEADER_COLOR": "RED"}))
        # pylint: disable=protected-access
        api._session.put.assert_called_once()
        _, keyword_arguments = api._session.put.call_args
        self.assertEqual(
            keyword_arguments["json"],
            {"items": [{"name": "CUSTOM_BANNER_HTML", "value": "value"},
                       {"name": "CUSTOM_HEADER_COLOR", "value": "RED"}]}
        )

    def test_a_refused_write_is_reported(self):
        """
        Which is what a credential without the Full Administrator role produces.
        """
        api = api_with([])
        # pylint: disable=protected-access
        api._session.put.side_effect = requests.RequestException("403")
        self.assertFalse(api.put_cm_config({"CUSTOM_BANNER_HTML": "value"}))


class MainTest(unittest.TestCase):
    """
    The entry point as a whole.
    """

    def run_main(self,
                 extra_arguments=None,
                 config_items=None,
                 resolved_credentials=None,
                 connects=True,
                 cluster_name="ozone-base-cluster"):
        """
        Runs `main` against a Cloudera Manager which answers with the given
        configuration, and returns the exit code together with the client.
        """
        api = api_with(
            config_items
            if config_items is not None
            else [{"name": "CUSTOM_BANNER_HTML", "value": None}]
        )
        with unittest.mock.patch(
                "coguard_cli.cloudera_integration.banner.resolve_credentials",
                new_callable=lambda: lambda _: resolved_credentials
        ), unittest.mock.patch(
            "coguard_cli.cloudera_integration.banner.connect_for_writing",
            new_callable=lambda: lambda _: api if connects else None
        ), unittest.mock.patch(
            "coguard_cli.cloudera_integration.banner.determine_cluster_name",
            new_callable=lambda: lambda *_: cluster_name
        ):
            exit_code = banner.main([
                "--cloudera-manager-url", "https://cm.example.com",
                "--cloudera-manager-user", "coguard"
            ] + (extra_arguments or []))
        return exit_code, api

    def test_a_banner_is_written(self):
        """
        The happy path, from a result file to a written parameter.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            exit_code, api = self.run_main(
                ["--result-file", path],
                resolved_credentials=credentials()
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        _, keyword_arguments = api._session.put.call_args
        written = keyword_arguments["json"]["items"][0]["value"]
        self.assertIn(banner.BLOCK_MARKER, written)
        self.assertIn("ozone-base-cluster", written)
        self.assertNotIn("<", written)

    def test_a_dry_run_writes_nothing(self):
        """
        The current banner is still read, so that what would be written is what
        is shown.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            exit_code, api = self.run_main(
                ["--result-file", path, "--dry-run"],
                resolved_credentials=credentials()
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        api._session.put.assert_not_called()

    def test_clear_removes_the_block_without_reading_a_result(self):
        """
        `--clear` does not need a scan to have run.
        """
        exit_code, api = self.run_main(
            ["--clear", "--result-file", "/nonexistent/result.json"],
            config_items=[{
                "name": "CUSTOM_BANNER_HTML",
                "value": "Production. | CoGuard: x"
            }],
            resolved_credentials=credentials()
        )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        _, keyword_arguments = api._session.put.call_args
        self.assertEqual(keyword_arguments["json"]["items"][0]["value"],
                         "Production.")

    def test_an_unchanged_banner_is_not_written_again(self):
        """
        A banner which already says this is left alone, so that a scheduled run
        does not produce a configuration revision every time. The timestamp is
        part of the text, so this is the `--clear` case of an already empty
        banner.
        """
        exit_code, api = self.run_main(
            ["--clear"],
            config_items=[{"name": "CUSTOM_BANNER_HTML", "value": ""}],
            resolved_credentials=credentials()
        )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        api._session.put.assert_not_called()

    def test_findings_colour_the_header_in_the_same_request(self):
        """
        The banner and the colour are one configuration revision, not two.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            exit_code, api = self.run_main(
                ["--result-file", path, "--header-color", "RED"],
                config_items=[{"name": "CUSTOM_BANNER_HTML", "value": None},
                              {"name": "CUSTOM_HEADER_COLOR", "value": "BLACK"}],
                resolved_credentials=credentials()
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        api._session.put.assert_called_once()
        _, keyword_arguments = api._session.put.call_args
        written = {item["name"]: item["value"]
                   for item in keyword_arguments["json"]["items"]}
        self.assertEqual(written["CUSTOM_HEADER_COLOR"], "RED")
        self.assertIn(banner.BLOCK_MARKER, written["CUSTOM_BANNER_HTML"])

    def test_a_clean_result_puts_the_header_colour_back(self):
        """
        The header does not stay red once the findings are gone.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [])
            exit_code, api = self.run_main(
                ["--result-file", path, "--header-color", "RED"],
                config_items=[{"name": "CUSTOM_BANNER_HTML", "value": None},
                              {"name": "CUSTOM_HEADER_COLOR", "value": "RED"}],
                resolved_credentials=credentials()
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        _, keyword_arguments = api._session.put.call_args
        written = {item["name"]: item["value"]
                   for item in keyword_arguments["json"]["items"]}
        self.assertEqual(written["CUSTOM_HEADER_COLOR"], "BLACK")

    def test_the_colour_is_written_even_when_the_banner_stays(self):
        """
        `--clear` against an already empty banner still has a red header to undo,
        and that is the case in which the two parameters do not agree on whether
        anything changed.
        """
        exit_code, api = self.run_main(
            ["--clear", "--header-color", "RED"],
            config_items=[{"name": "CUSTOM_BANNER_HTML", "value": ""},
                          {"name": "CUSTOM_HEADER_COLOR", "value": "RED"}],
            resolved_credentials=credentials()
        )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        _, keyword_arguments = api._session.put.call_args
        self.assertEqual(
            keyword_arguments["json"]["items"],
            [{"name": "CUSTOM_HEADER_COLOR", "value": "BLACK"}]
        )

    def test_a_cloudera_manager_without_the_colour_parameter_is_no_error(self):
        """
        The banner is what this command is for; a release without the colour
        parameter gets the banner and no colour, rather than an error.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            exit_code, api = self.run_main(
                ["--result-file", path, "--header-color", "RED"],
                config_items=[{"name": "CUSTOM_BANNER_HTML", "value": None}],
                resolved_credentials=credentials()
            )
        self.assertEqual(exit_code, EXIT_CLEAN)
        # pylint: disable=protected-access
        _, keyword_arguments = api._session.put.call_args
        written = {item["name"]: item["value"]
                   for item in keyword_arguments["json"]["items"]}
        self.assertIn("CUSTOM_BANNER_HTML", written)
        self.assertNotIn("CUSTOM_HEADER_COLOR", written)

    def test_credentials_which_cannot_be_resolved_are_an_error(self):
        """
        Without a url or a password there is nothing to do.
        """
        exit_code, _ = self.run_main(resolved_credentials=None)
        self.assertEqual(exit_code, EXIT_ERROR)

    def test_a_cloudera_manager_which_cannot_be_reached_is_an_error(self):
        """
        The connection is verified before anything is read.
        """
        exit_code, _ = self.run_main(resolved_credentials=credentials(),
                                     connects=False)
        self.assertEqual(exit_code, EXIT_ERROR)

    def test_a_missing_result_file_is_an_error(self):
        """
        A banner is not written from a scan which did not happen.
        """
        exit_code, api = self.run_main(
            ["--result-file", "/nonexistent/result.json"],
            resolved_credentials=credentials()
        )
        self.assertEqual(exit_code, EXIT_ERROR)
        # pylint: disable=protected-access
        api._session.put.assert_not_called()

    def test_a_configuration_which_cannot_be_read_is_an_error(self):
        """
        The current value has to be known before it is replaced.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            api = api_with([])
            # pylint: disable=protected-access
            api._session.get.side_effect = requests.RequestException("nope")
            with unittest.mock.patch(
                    "coguard_cli.cloudera_integration.banner."
                    "resolve_credentials",
                    new_callable=lambda: lambda _: credentials()
            ), unittest.mock.patch(
                "coguard_cli.cloudera_integration.banner.connect_for_writing",
                new_callable=lambda: lambda _: api
            ), unittest.mock.patch(
                "coguard_cli.cloudera_integration.banner."
                "determine_cluster_name",
                new_callable=lambda: lambda *_: "ozone-base-cluster"
            ):
                exit_code = banner.main([
                    "--cloudera-manager-url", "https://cm.example.com",
                    "--result-file", path
                ])
        self.assertEqual(exit_code, EXIT_ERROR)

    def test_a_cloudera_manager_without_the_parameter_is_an_error(self):
        """
        A Cloudera Manager release which has no custom banner is told apart from
        one whose banner is empty.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            exit_code, api = self.run_main(
                ["--result-file", path],
                config_items=[{"name": "OTHER", "value": "x"}],
                resolved_credentials=credentials()
            )
        self.assertEqual(exit_code, EXIT_ERROR)
        # pylint: disable=protected-access
        api._session.put.assert_not_called()

    def test_a_refused_write_is_an_error(self):
        """
        Which is the credential without the Full Administrator role.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            api = api_with([{"name": "CUSTOM_BANNER_HTML", "value": None}])
            # pylint: disable=protected-access
            api._session.put.side_effect = requests.RequestException("403")
            with unittest.mock.patch(
                    "coguard_cli.cloudera_integration.banner."
                    "resolve_credentials",
                    new_callable=lambda: lambda _: credentials()
            ), unittest.mock.patch(
                "coguard_cli.cloudera_integration.banner.connect_for_writing",
                new_callable=lambda: lambda _: api
            ), unittest.mock.patch(
                "coguard_cli.cloudera_integration.banner."
                "determine_cluster_name",
                new_callable=lambda: lambda *_: "ozone-base-cluster"
            ):
                exit_code = banner.main([
                    "--cloudera-manager-url", "https://cm.example.com",
                    "--result-file", path
                ])
        self.assertEqual(exit_code, EXIT_ERROR)


class ConnectForWritingTest(unittest.TestCase):
    """
    Creating the writing client.
    """

    def test_an_unusable_url_is_reported(self):
        """
        A url which is not a Cloudera Manager url does not raise out of the
        entry point.
        """
        self.assertIsNone(banner.connect_for_writing(credentials(url="")))

    def test_a_cloudera_manager_which_refuses_the_credentials_is_reported(self):
        """
        The connection check is what tells the credential apart from the url.
        """
        with unittest.mock.patch.object(
                banner.ClouderaManagerBannerApi,
                "check_connection",
                new_callable=lambda: lambda _: False
        ):
            self.assertIsNone(banner.connect_for_writing(credentials()))

    def test_a_reachable_cloudera_manager_produces_a_client(self):
        """
        The happy path.
        """
        with unittest.mock.patch.object(
                banner.ClouderaManagerBannerApi,
                "check_connection",
                new_callable=lambda: lambda _: True
        ):
            self.assertIsInstance(
                banner.connect_for_writing(credentials(verify_tls=False,
                                                       ca_cert=None)),
                banner.ClouderaManagerBannerApi
            )


class ArgumentParserTest(unittest.TestCase):
    """
    The command line.
    """

    def test_the_defaults_are_the_documented_ones(self):
        """
        The result file, the severity and the cap.
        """
        args = arguments()
        self.assertEqual(args.result_file, "result.json")
        self.assertEqual(args.minimum_severity, 1)
        self.assertEqual(args.max_services, banner.DEFAULT_MAX_SERVICES)
        self.assertFalse(args.clear)
        self.assertFalse(args.dry_run)

    def test_the_header_is_not_touched_unless_a_colour_is_given(self):
        """
        The parameter is Cloudera's way of telling instances of Cloudera Manager
        apart, so colouring it is opt-in.
        """
        self.assertIsNone(arguments().header_color)
        self.assertEqual(arguments().header_color_clean,
                         banner.DEFAULT_HEADER_COLOR_CLEAN)

    def test_a_colour_may_be_given_in_lower_case(self):
        """
        The values are Cloudera Manager's, which are upper case; what somebody
        types is not.
        """
        self.assertEqual(arguments(["--header-color", "red"]).header_color,
                         "RED")

    def test_a_colour_cloudera_manager_does_not_have_is_refused(self):
        """
        The ten values are the ones Cloudera Manager ships an asset for, and a
        value outside them would leave the header in an undefined state.
        """
        with self.assertRaises(SystemExit):
            arguments(["--header-color", "MAGENTA"])

    def test_the_cap_is_at_least_one_service(self):
        """
        A cap of zero would name nothing at all, so it is raised to one.
        """
        with tempfile.TemporaryDirectory() as directory:
            path = result_file(directory, [finding()])
            block, has_findings = banner.determine_block(
                arguments(["--max-services", "0", "--result-file", path]),
                "ozone-base-cluster"
            )
        self.assertIn("ozone_manager (1)", block)
        self.assertTrue(has_findings)


class DesiredHeaderColorTest(unittest.TestCase):
    """
    Deciding what the header bar is to be coloured in.
    """

    def test_without_the_option_the_header_is_left_alone(self):
        """
        The default, i.e. a banner run which only writes text.
        """
        self.assertIsNone(
            banner.desired_header_color(arguments(), True, "BLACK")
        )

    def test_findings_colour_the_header(self):
        """
        Which is the whole point of the option.
        """
        self.assertEqual(
            banner.desired_header_color(
                arguments(["--header-color", "RED"]), True, "BLACK"
            ),
            "RED"
        )

    def test_a_clean_result_puts_the_colour_back(self):
        """
        A configuration which has been fixed is not left with a red header.
        """
        self.assertEqual(
            banner.desired_header_color(
                arguments(["--header-color", "RED"]), False, "RED"
            ),
            "BLACK"
        )

    def test_a_colour_somebody_else_chose_is_not_taken_over(self):
        """
        A header coloured to tell this instance of Cloudera Manager apart from
        another one is not what a clean scan gets to reset.
        """
        self.assertIsNone(
            banner.desired_header_color(
                arguments(["--header-color", "RED"]), False, "TEAL"
            )
        )

    def test_the_colour_to_go_back_to_can_be_chosen(self):
        """
        For the instance which is normally recognised by its colour.
        """
        self.assertEqual(
            banner.desired_header_color(
                arguments(["--header-color", "RED",
                           "--header-color-clean", "TEAL"]),
                False,
                "RED"
            ),
            "TEAL"
        )

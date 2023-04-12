"""
Tests for the functions in the ConfigFileFinderOpenTelemetryCollector class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_open_telemetry_collector \
    import ConfigFileFinderOpenTelemetryCollector

class TestConfigFileFinderOpenTelemetryCollector(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderOpenTelemetryCollector module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(
            ConfigFileFinderOpenTelemetryCollector().get_service_name(),
            "opentelemetry_collector"
        )

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.lexists",
                new_callable=lambda: lambda location: False):
            config_file_finder_open_telemetry_collector = ConfigFileFinderOpenTelemetryCollector()
            self.assertIsNone(
                config_file_finder_open_telemetry_collector.\
                check_for_config_files_in_standard_location(
                "foo"
            ))

    def test_check_for_config_files_in_standard_location_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.lexists",
                new_callable=lambda: lambda location: True), \
            unittest.mock.patch(
                "shutil.copy"
            ), unittest.mock.patch(
                 ("coguard_cli.discovery.config_file_finders.config_file_"
                  "finder_open_telemetry_collector.ConfigFileFinderOpenTelemetryCollector."
                  "_create_temp_location_and_manifest_entry"),
                 new_callable=lambda: lambda a, b, c, d=None, e=None: ({
                     "foo": "bar",
                     "configFileList": []
                 }, "/etc/bar")
             ):
            config_file_finder_otel = ConfigFileFinderOpenTelemetryCollector()
            result = config_file_finder_otel.check_for_config_files_in_standard_location(
                "foo"
            )
            self.assertIsNotNone(result)
            self.assertEqual(result[0], {
                "foo": "bar",
                "configFileList": []
            })
            self.assertEqual(result[1], "/etc/bar")

    def test_check_for_config_files_filesystem_search_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            config_file_finder_otel_collector = ConfigFileFinderOpenTelemetryCollector()
            result = config_file_finder_otel_collector.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertListEqual(result, [])

    def test_check_for_config_files_filesystem_search_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("foo/etc", [], ["server.yaml"])]), \
                unittest.mock.patch(
                "os.path.exists",
                new_callable=lambda: lambda location: True), \
                unittest.mock.patch(
                "coguard_cli.discovery.config_file_finders.get_path_behind_symlinks",
                new_callable = lambda: lambda p, q: q), \
                unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(
                    read_data="receiversprocessorsexportersextensionsservice")
                ), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.config_file_"
                     "finder_open_telemetry_collector.ConfigFileFinderOpenTelemetryCollector."
                     "_create_temp_location_and_manifest_entry"),
                    new_callable=lambda: lambda a, b, c, d=None, e=None: (
                        {"foo": "bar"},
                        "/etc/bar"
                    )
                ):
            config_file_finder_otel = ConfigFileFinderOpenTelemetryCollector()
            result = config_file_finder_otel.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], {"foo": "bar"})
            self.assertEqual(result[0][1], "/etc/bar")

    def test_create_temp_location_and_manifest_entry(self):
        """
        Testing the creation of temporary locations and manifest entries.
        """
        def new_callable(prefix="/tmp"):
            return "/tmp/foo"
        with unittest.mock.patch(
                'tempfile.mkdtemp',
                new_callable=lambda: new_callable), \
             unittest.mock.patch(
                 'shutil.copy'
             ), \
             unittest.mock.patch(
                 'os.makedirs'
             ), \
             unittest.mock.patch(
                 ("coguard_cli.discovery.config_file_finders."
                  "extract_include_directives")
             ):
            config_file_finder_otel = ConfigFileFinderOpenTelemetryCollector()
            result = config_file_finder_otel._create_temp_location_and_manifest_entry(
                '/',
                ('config.yaml', "/etc")
            )
            self.assertEqual(result[1], "/tmp/foo")
            self.assertEqual(result[0]["serviceName"], "opentelemetry_collector")

    def test_check_call_command_in_container(self):
        """
        trivial test as function does nothing.
        """
        config_file_finder_otel = ConfigFileFinderOpenTelemetryCollector()
        result = config_file_finder_otel.check_call_command_in_container(
            "/", { "Config": {} }
        )
        self.assertEqual(result, [])

"""
Tests for the functions in the ConfigFileFinderHelm class
"""

import unittest
import unittest.mock
from coguard_cli.discovery.config_file_finders.config_file_finder_helm \
    import ConfigFileFinderHelm

class TestConfigFileFinderHelm(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderHelm module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderHelm().get_service_name(), "kubernetes")

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable=lambda: lambda location: False):
            config_file_finder_helm = ConfigFileFinderHelm()
            self.assertIsNone(
                config_file_finder_helm.check_for_config_files_in_standard_location(
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
                 ("coguard_cli.discovery.config_file_finders.config_file_finder"
                  "_helm.ConfigFileFinderHelm._create_temp_"
                  "location_and_mainfest_entry"),
                 new_callable=lambda: lambda a, b, c, d, e, f: ({"foo": "bar"}, "/etc/bar")
             ):
            config_file_finder_helm = ConfigFileFinderHelm()
            self.assertIsNone(
                config_file_finder_helm.check_for_config_files_in_standard_location(
                    "foo"
                )
            )

    def test_check_for_config_files_filesystem_search_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertListEqual(result, [])

    def test_find_charts_files_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm._find_charts_files(
                "foo"
            )
            self.assertListEqual(result, [])

    def test_find_charts_files_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["Chart.yaml"])]), \
            unittest.mock.patch(
                ("coguard_cli.discovery.config_file_finders.config_file_finder"
                 "_helm.ConfigFileFinderHelm._is_file_helm_yaml"),
                new_callable=lambda: lambda a, b: True):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm._find_charts_files(
                "foo"
            )
            self.assertListEqual(result, ["etc/Chart.yaml"])

    def test_check_for_config_files_filesystem_search_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                ("coguard_cli.discovery.config_file_finders.config_file_"
                 "finder_helm.ConfigFileFinderHelm._find_charts_files"),
                new_callable=lambda: lambda a, b: ["foo"]), \
                unittest.mock.patch(
                    ("coguard_cli.discovery.config_file_finders.config_file_finder"
                     "_helm.ConfigFileFinderHelm._create_temp_"
                     "location_and_mainfest_entry"),
                    new_callable=lambda: lambda a, b: ({"foo": "bar"}, "/etc/bar")
                ):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm.check_for_config_files_filesystem_search(
                "foo"
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][0], {"foo": "bar"})
            self.assertEqual(result[0][1], "/etc/bar")

    def test_check_call_command_in_container(self):
        """
        The function to test the attempted extraction of the my.cnf
        location from call commands.
        """
        config_file_finder_helm = ConfigFileFinderHelm()
        result = config_file_finder_helm.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "Cmd": [
                        "/bin/sh",
                        "-c",
                        "helm-server /etc/helm.conf"
                    ],
                    "WorkingDir": "",
                    "Entrypoint": [
                        "/docker-entrypoint.sh"
                    ],
                }
            }
        )
        self.assertListEqual(result, [])

    def test_is_file_helm_yaml_failed_to_load(self):
        """
        Tests if a file is a proper helm yaml file, heuristically.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(
                    read_data="receiversprocessorsexportersextensionsservice")):
            config_file_finder_helm = ConfigFileFinderHelm()
            self.assertFalse(config_file_finder_helm._is_file_helm_yaml("foo.txt"))

    def test_is_file_helm_yaml_proper_not_kube(self):
        """
        Tests if a file is a proper helm yaml file, heuristically.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(
                    read_data= "foo: bar")):
            config_file_finder_helm = ConfigFileFinderHelm()
            self.assertFalse(config_file_finder_helm._is_file_helm_yaml("foo.txt"))

    def test_is_file_helm_yaml_proper_kube(self):
        """
        Tests if a file is a proper helm yaml file, heuristically.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(
                    read_data= \
                    """
apiVersion: The chart API version (required)
name: The name of the chart (required)
version: A SemVer 2 version (required)
kubeVersion: A SemVer range of compatible Kubernetes versions (optional)
description: A single-sentence description of this project (optional)
type: The type of the chart (optional)
keywords:
  - A list of keywords about this project (optional)
home: The URL of this projects home page (optional)
sources:
  - A list of URLs to source code for this project (optional)
dependencies: # A list of the chart requirements (optional)
  - name: The name of the chart (nginx)
    version: The version of the chart ("1.2.3")
    repository: (optional) The repository URL ("https://example.com/charts") or alias ("@repo-name")
    condition: (optional) A yaml path that resolves to a boolean,
    tags: # (optional)
      - Tags can be used to group charts for enabling/disabling together
    import-values: # (optional)
      - ImportValues holds the mapping of source values to parent key to be imported.
    alias: (optional) Alias to be used for the chart. Useful when you have to add the
maintainers: # (optional)
  - name: The maintainers name (required for each maintainer)
    email: The maintainers email (optional for each maintainer)
    url: A URL for the maintainer (optional for each maintainer)
icon: A URL to an SVG or PNG image to be used as an icon (optional).
appVersion: The version of the app that this contains (optional).
deprecated: Whether this chart is deprecated (optional, boolean)
annotations:
  example: A list of annotations keyed by name (optional).
                    """)):
            config_file_finder_helm = ConfigFileFinderHelm()
            self.assertTrue(config_file_finder_helm._is_file_helm_yaml("foo.txt"))

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
                 'coguard_cli.docker_dao.get_kubernetes_translation_from_helm',
                 new_callable=lambda: lambda dir: "foo: bar"
             ), \
             unittest.mock.patch(
                'builtins.open'
             ):
            config_file_finder_helm = ConfigFileFinderHelm()
            result = config_file_finder_helm._create_temp_location_and_mainfest_entry(
                '/'
            )
            self.assertEqual(result[1], "/tmp/foo")
            self.assertEqual(result[0]["serviceName"], "kubernetes")

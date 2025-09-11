"""
This is a testing module for the common functions
inside the image_check module.
"""

import unittest
import unittest.mock
import pathlib
import subprocess
from coguard_cli import auth
from coguard_cli import folder_scan
from coguard_cli.discovery.config_file_finders.config_file_finder_nginx \
    import ConfigFileFinderNginx
from coguard_cli.discovery.config_file_finders.config_file_finder_netlify \
    import ConfigFileFinderNetlify

class TestCommonImageCheckingFunc(unittest.TestCase):
    """
    The TestCase class with the common functions to test
    """

    def test_create_zip_to_upload_folder_none(self):
        """
        This checks that None is being returned if the image cannot be
        stored on the file-system.
        """
        with unittest.mock.patch(
                "coguard_cli.docker_dao.store_image_file_system",
                 new_callable = lambda: lambda x: None):
            result = folder_scan.create_zip_to_upload_from_file_system(
                None
            )
            self.assertIsNone(result)

    def test_create_zip_to_upload_folder_collected(self):
        """
        Proper test of create_zip_to_upload_from_docker_image.
        """
        def new_tempfile(prefix, suffix):
            return ("foo", "bar")
        with unittest.mock.patch(
                "tempfile.mkstemp",
                 new_callable = lambda: new_tempfile), \
             unittest.mock.patch(
                 "zipfile.ZipFile",
                 new_callable = lambda: lambda x, y: unittest.mock.mock_open(
                     mock=unittest.mock.MagicMock()
                 )), \
             unittest.mock.patch(
                 "os.walk",
                 new_callable=lambda: lambda x: [("/etc/foo/bar", [], ['foo.conf'])]), \
             unittest.mock.patch(
                 "os.close",
                 new_callable=lambda: lambda x: x), \
             unittest.mock.patch(
                 "shutil.rmtree"
             ):
            result, _ = folder_scan.create_zip_to_upload_from_file_system(
                ("/foo/bar/baz", {})
            )
            self.assertIsNotNone(result)
            self.assertEqual(result, "bar")

    def test_find_configuration_files_and_collect_none_result(self):
        """
        The test function to find configuration files using the
        available finder classes. Tests the case where none was found
        """
        with unittest.mock.patch(
                'coguard_cli.discovery.config_file_finder_factory.config_file_finder_factory',
                new_callable=lambda: lambda: [ConfigFileFinderNginx()]), \
             unittest.mock.patch(
                ('coguard_cli.discovery.config_file_finders.config_file_finder_nginx.'
                 'ConfigFileFinderNginx.find_configuration_files'),
                 new_callable=lambda: lambda x, y, z: []):
            self.assertIsNone(folder_scan.find_configuration_files_and_collect(
                "folder-name",
                "foo"
            ))

    def test_find_configuration_files_and_collect(self):
        """
        The test function to find configuration files using the
        available finder classes.
        """
        with unittest.mock.patch(
                'coguard_cli.discovery.config_file_finder_factory.config_file_finder_factory',
                new_callable=lambda: lambda: [ConfigFileFinderNginx()]), \
             unittest.mock.patch(
                ('coguard_cli.discovery.config_file_finders.config_file_finder_nginx.'
                 'ConfigFileFinderNginx.find_configuration_files'),
                 new_callable=lambda: lambda x, y, z: [
                     ({"foo": "bar", "configFileList": []}, "/etc/foo/bar")
                 ]), \
             unittest.mock.patch(
                 'tempfile.mkdtemp',
                 new_callable = lambda: lambda prefix: "/foo"
             ), \
             unittest.mock.patch(
                 'os.mkdir'
             ), \
             unittest.mock.patch(
                 'shutil.copytree'
             ), \
             unittest.mock.patch(
                 'shutil.rmtree'
             ), \
             unittest.mock.patch(
                 'builtins.open',
                 unittest.mock.mock_open()
             ), \
             unittest.mock.patch(
                ('coguard_cli.image_check.extract_docker_file_and_store'),
                 new_callable=lambda: lambda x: None):
            result, _ = folder_scan.find_configuration_files_and_collect(
                "image-name",
                "foo"
            )
            self.assertIsNotNone(result)
            self.assertEqual(result, "/foo")

    def test_find_configuration_files_and_collect_cluster_service(self):
        """
        The test function to find configuration files using the
        available finder classes.
        """
        with unittest.mock.patch(
                'coguard_cli.discovery.config_file_finder_factory.config_file_finder_factory',
                new_callable=lambda: lambda: [ConfigFileFinderNetlify()]), \
             unittest.mock.patch(
                ('coguard_cli.discovery.config_file_finders.config_file_finder_netlify.'
                 'ConfigFileFinderNetlify.find_configuration_files'),
                 new_callable=lambda: lambda x, y, z: [
                     ({"foo": "bar", "configFileList": []}, "/etc/foo/bar")
                 ]), \
             unittest.mock.patch(
                 'tempfile.mkdtemp',
                 new_callable = lambda: lambda prefix: "/foo"
             ), \
             unittest.mock.patch(
                 'os.mkdir'
             ), \
             unittest.mock.patch(
                 'shutil.copytree'
             ), \
             unittest.mock.patch(
                 'shutil.rmtree'
             ), \
             unittest.mock.patch(
                 'builtins.open',
                 unittest.mock.mock_open()
             ), \
             unittest.mock.patch(
                ('coguard_cli.image_check.extract_docker_file_and_store'),
                 new_callable=lambda: lambda x: None):
            result, _ = folder_scan.find_configuration_files_and_collect(
                "image-name",
                "foo"
            )
            self.assertIsNotNone(result)
            self.assertEqual(result, "/foo")

    def test_find_images_recursively_empty_dict(self):
        """
        Testing the finding of images inside a dictionary.
        """
        self.assertListEqual(
            folder_scan._find_images_recursively(
                {}
            ),
            []
        )

    def test_find_images_recursively_empty_list(self):
        """
        Testing the finding of images inside a dictionary.
        """
        self.assertListEqual(
            folder_scan._find_images_recursively(
                []
            ),
            []
        )

    def test_find_images_non_trivial_dict(self):
        """
        Testing the finding of images inside a dictionary.
        """
        self.assertListEqual(
            folder_scan._find_images_recursively(
                {
                    "foo": "bar",
                    "biz": {
                        "more_foo": "more_bar"
                    }
                }
            ),
            []
        )

    def test_find_images_non_trivial_list(self):
        """
        Testing the finding of images inside a list.
        """
        self.assertListEqual(
            folder_scan._find_images_recursively(
                [{
                    "foo": "bar",
                    "biz": {
                        "more_foo": "more_bar"
                    }
                }]
            ),
            []
        )

    def test_find_images_non_trivial_dict_with_result(self):
        """
        Testing the finding of images inside a dictionary.
        """
        self.assertListEqual(
            folder_scan._find_images_recursively(
                {
                    "foo": "bar",
                    "biz": {
                        "more_foo": "more_bar",
                        "image": "redis"
                    }
                }
            ),
            ["redis"]
        )

    def test_find_images_non_trivial_dict_with_result_nested_list(self):
        """
        Testing the finding of images inside a dictionary.
        """
        self.assertListEqual(
            folder_scan._find_images_recursively(
                {
                    "foo": "bar",
                    "biz": [{
                        "more_foo": "more_bar",
                        "image": "redis"
                    }]
                }
            ),
            ["redis"]
        )

    def test_find_and_extract_docker_images_from_config_files_empty_list(self):
        """
        Testing find and extract docker images with an empty list
        """
        self.assertListEqual(
            folder_scan._find_and_extract_docker_images_from_config_files(
                []
            ),
            []
        )

    def test_find_and_extract_docker_images_from_config_files_non_empty_list(self):
        """
        Testing find and extract docker images with an empty list
        """
        config_file_list = [
            ("foo", "bar")
        ]
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(read_data="[]")):
            self.assertListEqual(
                folder_scan._find_and_extract_docker_images_from_config_files(
                    config_file_list
                ),
                []
            )

    def test_find_and_extract_docker_images_from_config_files_non_trivial(self):
        """
        Testing find and extract docker images with an empty list
        """
        yaml_data = """
        foo: "bar"
        biz:
         - more_foo: more_bar
           image: redis
        """.replace("        ", "")
        config_file_list = [
            ("foo", "bar")
        ]
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(read_data=yaml_data)):
            self.assertListEqual(
                folder_scan._find_and_extract_docker_images_from_config_files(
                    config_file_list
                ),
                [("redis", "bar")]
            )

    def test_extract_included_docker_images_none_input(self):
        """
        Testing the extraction of included Docker images.
        """
        self.assertListEqual(
            folder_scan.extract_included_docker_images(
                None
            ),
            []
        )

    def test_extract_included_docker_images_valid_input(self):
        """
        Testing the extraction of included Docker images.
        """
        with unittest.mock.patch(
                "coguard_cli.folder_scan._find_and_extract_docker_images_from_config_files",
                new_callable = lambda: lambda l: ["kubectl"]
        ):
            self.assertListEqual(
                folder_scan.extract_included_docker_images(
                    ("foo/bar", {})
                ),
                ["kubectl"]
            )

    def test_extract_included_docker_images_valid_nontrivial_input(self):
        """
        Testing the extraction of included Docker images.
        """
        manifest = """
        {
          "name": "test cluster",
          "customerId": "test customer",
          "machines":
          {
            "us-jfk-001": {
              "id": "1",
              "hostName": "test.test-customer.com",
              "externalIp": "127.0.0.1",
              "internalIp": "127.0.0.1",
              "services": {
                "Postgres": {
                  "version": "1.0",
                  "serviceName": "postgres",
                  "configFileList": [
                    {
                      "fileName": "postgresql.conf",
                      "defaultFileName": "postgresql.conf",
                      "subPath": ".",
                      "configFileType": "properties"
                    }
                  ]
                }
              }
            }
          }
        }
        """
        with unittest.mock.patch(
                "coguard_cli.folder_scan._find_and_extract_docker_images_from_config_files",
                new_callable = lambda: lambda l: ["kubectl"]
        ):
            self.assertListEqual(
                folder_scan.extract_included_docker_images(
                    ("foo/bar", {})
                ),
                ["kubectl"]
            )

    def test_extract_included_docker_images_valid_nontrivial_input_cluster_service(self):
        """
        Testing the extraction of included Docker images.
        """
        manifest = """
        {
          "name": "test cluster",
          "customerId": "test customer",
          "machines":
          {
            "us-jfk-001": {
              "id": "1",
              "hostName": "test.test-customer.com",
              "externalIp": "127.0.0.1",
              "internalIp": "127.0.0.1",
              "services": {
                "Kubernetes": {
                  "version": "1.0",
                  "serviceName": "kubernetes",
                  "configFileList": [
                    {
                      "fileName": "kubelet-configuration.yaml",
                      "defaultFileName": "kubelet-configuration.yaml",
                      "subPath": ".",
                      "configFileType": "yaml"
                    }
                  ]
                }
              }
            }
          }
        }
        """
        with unittest.mock.patch(
                "coguard_cli.folder_scan._find_and_extract_docker_images_from_config_files",
                new_callable = lambda: lambda l: ["kubectl"]
        ):
            self.assertListEqual(
                folder_scan.extract_included_docker_images(
                    ("foo/bar", {})
                ),
                ["kubectl"]
            )

    def test_filter_config_file_list_empty_list(self):
        """
        Testing the filter_config_file_list helper function with an empty list.
        """
        self.assertListEqual(
            folder_scan.filter_config_file_list(
                [],
                ["*"]
            ),
            []
        )

    def test_filter_config_file_list_non_empty_wildcard(self):
        """
        Testing the filter_config_file_list helper function with a non-empty list, and wildcard match.
        """
        with unittest.mock.patch(
                 "os.remove",
                 new_callable=lambda: lambda x: None
        ), \
        unittest.mock.patch(
                 "shutil.rmtree",
                 new_callable=lambda: lambda tmp_path, ignore_errors: None
        ):
            self.assertListEqual(
                folder_scan.filter_config_file_list(
                    [
                        (
                            {
                                "version": "1.0",
                                "serviceName": "nginx",
                                "configFileList": [
                                    {"fileName": "nginx.conf",
                                     "defaultFileName": "nginx.conf",
                                     "subPath": "./apps/remix-ide",
                                     "configFileType": "nginx"}
                                ],
                                "complimentaryFileList": []
                            },
                            "/tmp/coguard-cli-nginxoa0223ra"
                        )
                    ],
                    ["*"]
                ),
                []
            )

    def test_filter_config_file_list_non_empty_no_chagnes(self):
        """
        Testing the filter_config_file_list helper function with a non-empty list, and
        a non-wildcard-match.
        """
        orig_list = [
            (
                {
                    "version": "1.0",
                    "serviceName": "nginx",
                    "configFileList": [
                        {"fileName": "nginx.conf",
                         "defaultFileName": "nginx.conf",
                         "subPath": "./apps/remix-ide",
                         "configFileType": "nginx"}
                    ],
                    "complimentaryFileList": []
                },
                "/tmp/coguard-cli-nginxoa0223ra"
            )
        ]
        with unittest.mock.patch(
                 "os.remove",
                 new_callable=lambda: lambda x: None
        ), \
        unittest.mock.patch(
                 "shutil.rmtree",
                 new_callable=lambda: lambda tmp_path, ignore_errors: None
        ):
            self.assertListEqual(
                folder_scan.filter_config_file_list(
                    orig_list,
                    ["foobar"]
                ),
                orig_list
            )

    def test_filter_collected_service_results_none_ignore_list(self):
        """
        Testing the `filter_collected_service_results_none_ignore_list` function.
        The input here will be a regular dictionary, but an empty ignore-list.
        """
        input_dict = {
            "nginx":
            (
                False,
                [
                    (
                        {
                            "version": "1.0",
                            "serviceName": "nginx",
                            "configFileList": [
                                {
                                    "fileName": "nginx.conf",
                                    "defaultFileName": "nginx.conf",
                                    "subPath": "./apps/remix-ide",
                                    "configFileType": "nginx"
                                }
                            ],
                            "complimentaryFileList": []
                        },
                        "/tmp/coguard-cli-nginxoa0223ra"
                    )
                ]
            )
        }
        ignore_list = []
        folder_scan.filter_collected_service_results(
            input_dict,
            ignore_list
        )
        self.assertDictEqual(
            input_dict,
            {
                "nginx":
                (
                    False,
                    [
                        (
                            {
                                "version": "1.0",
                                "serviceName": "nginx",
                                "configFileList": [
                                    {
                                        "fileName": "nginx.conf",
                                        "defaultFileName": "nginx.conf",
                                        "subPath": "./apps/remix-ide",
                                        "configFileType": "nginx"
                                }
                                ],
                                "complimentaryFileList": []
                            },
                            "/tmp/coguard-cli-nginxoa0223ra"
                        )
                    ]
                )
            }
        )

    def test_filter_collected_service_results_wildcard_ignore_list(self):
        """
        Testing the `filter_collected_service_results_none_ignore_list` function.
        The input here will be a regular dictionary, and a wildcard ignore-list.
        """
        input_dict = {
            "nginx":
            (
                False,
                [
                    (
                        {
                            "version": "1.0",
                            "serviceName": "nginx",
                            "configFileList": [
                                {
                                    "fileName": "nginx.conf",
                                    "defaultFileName": "nginx.conf",
                                    "subPath": "./apps/remix-ide",
                                    "configFileType": "nginx"
                                }
                            ],
                            "complimentaryFileList": []
                        },
                        "/tmp/coguard-cli-nginxoa0223ra"
                    )
                ]
            )
        }
        ignore_list = ["*"]
        with unittest.mock.patch(
                 "os.remove",
                 new_callable=lambda: lambda x: None
        ), \
        unittest.mock.patch(
                 "shutil.rmtree",
                 new_callable=lambda: lambda tmp_path, ignore_errors: None
        ):
            folder_scan.filter_collected_service_results(
                input_dict,
                ignore_list
            )
            self.assertDictEqual(
                input_dict,
                {}
            )

    def test_filter_collected_service_results_normal_ignore_list(self):
        """
        Testing the `filter_collected_service_results_none_ignore_list` function.
        The input here will be a regular dictionary, but an empty ignore-list.
        """
        input_dict = {
            "nginx":
            (
                False,
                [
                    (
                        {
                            "version": "1.0",
                            "serviceName": "nginx",
                            "configFileList": [
                                {
                                    "fileName": "nginx.conf",
                                    "defaultFileName": "nginx.conf",
                                    "subPath": "./apps/remix-ide",
                                    "configFileType": "nginx"
                                }
                            ],
                            "complimentaryFileList": []
                        },
                        "/tmp/coguard-cli-nginxoa0223ra"
                    )
                ]
            )
        }
        ignore_list = ["foobar"]
        folder_scan.filter_collected_service_results(
            input_dict,
            ignore_list
        )
        self.assertDictEqual(
            input_dict,
            {
                "nginx":
                (
                    False,
                    [
                        (
                            {
                                "version": "1.0",
                                "serviceName": "nginx",
                                "configFileList": [
                                    {
                                        "fileName": "nginx.conf",
                                        "defaultFileName": "nginx.conf",
                                        "subPath": "./apps/remix-ide",
                                        "configFileType": "nginx"
                                }
                                ],
                                "complimentaryFileList": []
                            },
                            "/tmp/coguard-cli-nginxoa0223ra"
                        )
                    ]
                )
            }
        )

    def test_perform_folder_fix_folder_scan_not_enterprise(self):
        """
        Testing the perform_folder_fix function when a non-enterprise license is used.
        """
        zip_upload = unittest.mock.Mock()
        rmtree = unittest.mock.Mock()
        upload_and_fix = unittest.mock.Mock()
        with unittest.mock.patch(
                'coguard_cli.folder_scan.find_configuration_files_and_collect',
                new_callable=lambda: lambda a, b: (a, b)
        ), \
        unittest.mock.patch(
                'coguard_cli.folder_scan.create_zip_to_upload_from_file_system',
                new_callable=lambda: zip_upload
        ), \
        unittest.mock.patch(
            'coguard_cli.util.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            folder_scan.perform_folder_fix(
                "foo",
                auth.enums.DealEnum.DEV,
                "token",
                "coguard",
                "portal.coguard.io"
            )
            self.assertEqual(zip_upload.call_count, 0)
            self.assertEqual(rmtree.call_count, 0)
            self.assertEqual(upload_and_fix.call_count, 0)

    def test_perform_folder_fix_folder_scan_none(self):
        """
        Testing the perform_folder_fix function when there are no collected config
        files.
        """
        zip_upload = unittest.mock.Mock()
        rmtree = unittest.mock.Mock()
        upload_and_fix = unittest.mock.Mock()
        with unittest.mock.patch(
                'coguard_cli.folder_scan.find_configuration_files_and_collect',
                new_callable=lambda: lambda a, b, ignore_list: None
        ), \
        unittest.mock.patch(
                'coguard_cli.folder_scan.create_zip_to_upload_from_file_system',
                new_callable=lambda: zip_upload
        ), \
        unittest.mock.patch(
            'coguard_cli.util.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            folder_scan.perform_folder_fix(
                "foo",
                auth.enums.DealEnum.ENTERPRISE,
                "token",
                "coguard",
                "portal.coguard.io"
            )
            self.assertEqual(zip_upload.call_count, 0)
            self.assertEqual(rmtree.call_count, 0)
            self.assertEqual(upload_and_fix.call_count, 0)

    def test_perform_folder_fix_zip_candidate_none(self):
        """
        Testing the perform_folder_fix function when there are no collected config
        files.
        """
        rmtree = unittest.mock.Mock()
        upload_and_fix = unittest.mock.Mock()
        with unittest.mock.patch(
                'coguard_cli.folder_scan.find_configuration_files_and_collect',
                new_callable=lambda: lambda a, b, ignore_list: ("location", "something else")
        ), \
        unittest.mock.patch(
                'coguard_cli.folder_scan.create_zip_to_upload_from_file_system',
                new_callable=lambda: lambda a: None
        ), \
        unittest.mock.patch(
            'coguard_cli.util.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            folder_scan.perform_folder_fix(
                "foo",
                auth.enums.DealEnum.ENTERPRISE,
                "token",
                "coguard",
                "portal.coguard.io"
            )
            self.assertEqual(rmtree.call_count, 1)
            self.assertEqual(upload_and_fix.call_count, 0)

    def test_perform_folder_fix_zip_candidate(self):
        """
        Testing the perform_folder_fix function when there are no collected config
        files.
        """
        rmtree = unittest.mock.Mock()
        upload_and_fix = unittest.mock.Mock()
        with unittest.mock.patch(
                'coguard_cli.folder_scan.find_configuration_files_and_collect',
                new_callable=lambda: lambda a, b, ignore_list: ("location", "something else")
        ), \
        unittest.mock.patch(
                'coguard_cli.folder_scan.create_zip_to_upload_from_file_system',
                new_callable=lambda: lambda a: "foo.zip"
        ), \
        unittest.mock.patch(
            'coguard_cli.util.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            folder_scan.perform_folder_fix(
                "foo",
                auth.enums.DealEnum.ENTERPRISE,
                "token",
                "coguard",
                "portal.coguard.io"
            )
            self.assertEqual(rmtree.call_count, 1)
            self.assertEqual(upload_and_fix.call_count, 1)

    @unittest.mock.patch.object(pathlib.Path, "exists", return_value=False)
    @unittest.mock.patch("subprocess.run")
    def test_cdk_synth_not_existing(self, mock_run, mock_exists):
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = b""
        mock_run.return_value = mock_result
        folder_scan._find_and_extract_cdk_json("/fake/path")
        mock_run.assert_not_called()

    @unittest.mock.patch.object(pathlib.Path, "exists", return_value=True)
    @unittest.mock.patch("subprocess.run")
    def test_cdk_synth_success(self, mock_run, mock_exists):
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = b""
        mock_run.return_value = mock_result

        with self.assertLogs(level="INFO") as cm:
            folder_scan._find_and_extract_cdk_json("/fake/path")

        self.assertIn("cdk synth succeeded", "\n".join(cm.output))
        mock_run.assert_called_once_with(
            ["cdk", "synth"],
            cwd="/fake/path",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    @unittest.mock.patch.object(pathlib.Path, "exists", return_value=True)
    @unittest.mock.patch("subprocess.run")
    def test_cdk_synth_failure(self, mock_run, mock_exists):
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"something went wrong"
        mock_run.return_value = mock_result

        with self.assertLogs(level="WARNING") as cm:
            folder_scan._find_and_extract_cdk_json("/fake/path")

        log_output = "\n".join(cm.output)
        self.assertIn("cdk synth failed", log_output)
        self.assertIn("something went wrong", log_output)

    @unittest.mock.patch.object(pathlib.Path, "exists", return_value=True)
    @unittest.mock.patch("subprocess.run", side_effect=OSError("cdk not found"))
    def test_cdk_synth_exception(self, mock_run, mock_exists):
        with self.assertLogs(level="ERROR") as cm:
            folder_scan._find_and_extract_cdk_json("/fake/path")

        log_output = "\n".join(cm.output)
        self.assertIn("Unexpected error", log_output)
        self.assertIn("cdk not found", log_output)

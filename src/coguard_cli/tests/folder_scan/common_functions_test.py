"""
This is a testing module for the common functions
inside the image_check module.
"""

import unittest
import unittest.mock
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

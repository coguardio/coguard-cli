"""
This is a testing module for the common functions
inside the image_check module.
"""

import unittest
import unittest.mock
from coguard_cli import image_check
from coguard_cli.auth.util import DealEnum
from coguard_cli.discovery.config_file_finders.config_file_finder_nginx \
    import ConfigFileFinderNginx
from coguard_cli.discovery.config_file_finders.config_file_finder_netlify \
    import ConfigFileFinderNetlify

class TestCommonImageCheckingFunc(unittest.TestCase):
    """
    The TestCase class with the common functions to test
    """

    def test_create_zip_to_upload_docker_image_docker_creation_failed(self):
        """
        This checks that None is being returned if the docker image
        creation fails.
        """
        with unittest.mock.patch(
                "coguard_cli.docker_dao.create_docker_image",
                new_callable = lambda: lambda x, y: None):
            result = image_check.create_zip_to_upload_from_docker_image(
                None
            )
            self.assertIsNone(result)

    def test_create_zip_to_upload_docker_image_collected(self):
        """
        Proper test of create_zip_to_upload_from_docker_image.
        """
        def new_tempfile(prefix, suffix):
            return ("foo", "bar")
        with unittest.mock.patch(
                "tempfile.mkstemp",
                 new_callable = lambda: new_tempfile), \
             unittest.mock.patch(
                 "os.close",
                 new_callable=lambda: lambda x: x), \
             unittest.mock.patch(
                 "zipfile.ZipFile",
                 new_callable = lambda: lambda x, y: unittest.mock.mock_open(
                     mock=unittest.mock.MagicMock()
                 )):
            result, _ = image_check.create_zip_to_upload_from_docker_image(
                ("/foo/bar/baz", {})
            )
            self.assertIsNotNone(result)
            self.assertEqual(result, "bar")


    def test_extract_image_to_filesystem_docker_inspect_failed(self):
        """
        This checks that None is being returned if the docker image
        inspection fails.
        """
        with unittest.mock.patch(
                "coguard_cli.docker_dao.create_docker_image",
                new_callable = lambda: lambda x: "fooImage"), \
             unittest.mock.patch(
                "coguard_cli.docker_dao.get_inspect_result",
                 new_callable = lambda: lambda x: None):
            result = image_check.extract_image_to_file_system(
                "foo"
            )
            self.assertIsNone(result)

    def test_extract_image_to_filesystem_get_file_store_failed(self):
        """
        This checks that None is being returned if the image cannot be
        stored on the file-system.
        """
        with unittest.mock.patch(
                "coguard_cli.docker_dao.create_docker_image",
                new_callable = lambda: lambda x: "fooImage"), \
             unittest.mock.patch(
                "coguard_cli.docker_dao.get_inspect_result",
                 new_callable = lambda: lambda x: {"foo": "bar"}), \
             unittest.mock.patch(
                "coguard_cli.docker_dao.store_image_file_system",
                 new_callable = lambda: lambda x: None):
            result = image_check.extract_image_to_file_system(
                "foo"
            )
            self.assertIsNone(result)

    def test_extract_image_to_filesystem_collected_location_none(self):
        """
        This checks that None is being returned if the find_configuration_and_collect
        function is returning None.
        """
        with unittest.mock.patch(
                "coguard_cli.docker_dao.create_docker_image",
                new_callable = lambda: lambda x: "fooImage"), \
             unittest.mock.patch(
                "coguard_cli.docker_dao.get_inspect_result",
                 new_callable = lambda: lambda x: {"foo": "bar"}), \
             unittest.mock.patch(
                "coguard_cli.docker_dao.store_image_file_system",
                 new_callable = lambda: lambda x: "/foo/bar"):
            result = image_check.extract_image_to_file_system(
                "foo"
            )
            self.assertEqual(
                result,
                ("/foo/bar", {"foo": "bar"}, "fooImage")
            )

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
                 new_callable=lambda: lambda x, y, z: []), \
             unittest.mock.patch(
                ('coguard_cli.image_check.extract_docker_file_and_store'),
                 new_callable=lambda: lambda x: None):
            self.assertIsNone(image_check.find_configuration_files_and_collect(
                "image-name",
                "foo",
                "/tmp/foo",
                {"bla": "bla"}
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
            result, _ = image_check.find_configuration_files_and_collect(
                "image-name",
                "foo",
                "/tmp/foo",
                {"bla": "bla"}
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
            result, _ = image_check.find_configuration_files_and_collect(
                "image-name",
                "foo",
                "/tmp/foo",
                {"bla": "bla"}
            )
            self.assertIsNotNone(result)
            self.assertEqual(result, "/foo")

    def test_extract_docker_file_and_store_none(self):
        """
        Tests the functionality to extract a docker file and store it.
        This checks the function where None is returned.
        """
        with unittest.mock.patch(
                'coguard_cli.docker_dao.extract_docker_file',
                new_callable=lambda: lambda x: None):
            self.assertIsNone(image_check.extract_docker_file_and_store("foo"))

    def test_extract_docker_file_and_store(self):
        """
        Tests the functionality to extract a docker file and store it.
        """
        with unittest.mock.patch(
                'coguard_cli.docker_dao.extract_docker_file',
                new_callable=lambda: lambda x: "foo"), \
             unittest.mock.patch(
                 'tempfile.mkdtemp',
                 new_callable=lambda: lambda prefix: "bar"
             ), \
             unittest.mock.patch(
                 'builtins.open',
                 unittest.mock.mock_open()
             ):
            self.assertEqual(
                image_check.extract_docker_file_and_store("foo"),
                ({
                    "version": "1.0",
                    "serviceName": "dockerfile",
                    "configFileList": [
                        {
                            "fileName": "Dockerfile",
                            "defaultFileName": "Dockerfile",
                            "subPath": ".",
                            "configFileType": "dockerfile"
                        }
                    ],
                    "complimentaryFileList": []
                }, "bar")
            )

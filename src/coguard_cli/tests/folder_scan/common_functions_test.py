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
                None,
                "foo"
            )
            self.assertIsNone(result)

    def test_create_zip_to_upload_folder_collected(self):
        """
        Proper test of create_zip_to_upload_from_docker_image.
        """
        def new_tempfile(prefix, suffix):
            return ("foo", "bar")
        with unittest.mock.patch(
                "coguard_cli.folder_scan.find_configuration_files_and_collect",
                 new_callable = lambda: lambda x, y: ("/foo/bar/baz", {})), \
             unittest.mock.patch(
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
                "foo",
                "foo"
            )
            self.assertIsNotNone(result)
            self.assertEqual(result, "bar")

    def test_create_zip_to_upload_folder_collected_none(self):
        """
        Proper test of create_zip_to_upload_from_docker_image.
        """
        def new_tempfile(prefix, suffix):
            return ("foo", "bar")
        with unittest.mock.patch(
                "coguard_cli.folder_scan.find_configuration_files_and_collect",
                 new_callable = lambda: lambda x, y: None), \
             unittest.mock.patch(
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
            result = folder_scan.create_zip_to_upload_from_file_system(
                "foo",
                "foo"
            )
            self.assertIsNone(result)

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
                 new_callable=lambda: lambda x, y, z: [({"foo": "bar"}, "/etc/foo/bar")]), \
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
                 new_callable=lambda: lambda x, y, z: [({"foo": "bar"}, "/etc/foo/bar")]), \
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

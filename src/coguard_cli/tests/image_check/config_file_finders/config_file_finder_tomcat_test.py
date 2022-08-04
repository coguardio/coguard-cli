"""
Tests for the functions in the ConfigFileFinderPostgres class
"""

import unittest
import unittest.mock
from coguard_cli.image_check.config_file_finders.config_file_finder_tomcat \
    import ConfigFileFinderTomcat

class TestConfigFileFinderTomcat(unittest.TestCase):
    """
    The class for testing the ConfigFileFinderTomcat module
    """

    def test_get_service_name(self):
        """
        Tests that the correct service name is being returned.
        """
        self.assertEqual(ConfigFileFinderTomcat().get_service_name(), "tomcat")

    def test_check_for_config_files_in_standard_location_not_existing(self):
        """
        This checks for the standard location test and sees if the file is
        existent or not.
        """
        with unittest.mock.patch(
                "os.path.lexists",
                new_callable=lambda: lambda location: False):
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            self.assertIsNone(
                config_file_finder_tomcat.check_for_config_files_in_standard_location(
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
                 ("coguard_cli.image_check.config_file_finders.config_file_"
                  "finder_tomcat.ConfigFileFinderTomcat._create_temp_"
                  "location_and_mainfest_entry"),
                 new_callable=lambda: lambda a, b, c, d=None, e=None: ({
                     "foo": "bar",
                     "configFileList": []
                 }, "/etc/bar")
             ):
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            result = config_file_finder_tomcat.check_for_config_files_in_standard_location(
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
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            result = config_file_finder_tomcat.check_for_config_files_filesystem_search(
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
                new_callable=lambda: lambda location: [("etc", [], ["server.xml"])]), \
                unittest.mock.patch(
                    ("coguard_cli.image_check.config_file_finders.config_file_"
                     "finder_tomcat.ConfigFileFinderTomcat._create_temp_"
                     "location_and_mainfest_entry"),
                    new_callable=lambda: lambda a, b, c, d=None, e=None: ({"foo": "bar"}, "/etc/bar")
                ):
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            result = config_file_finder_tomcat.check_for_config_files_filesystem_search(
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
                 ("coguard_cli.image_check.config_file_finders."
                  "extract_include_directives")
             ):
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            result = config_file_finder_tomcat._create_temp_location_and_mainfest_entry(
                '/',
                ('server.xml', "/etc")
            )
            self.assertEqual(result[1], "/tmp/foo")
            self.assertEqual(result[0]["serviceName"], "tomcat")

    def test_check_call_command_in_container_no_entrypoint_or_cmd(self):
        """
        The function to test the attempted extraction of the tomcatql.conf
        location from call commands.
        """
        config_file_finder_tomcat = ConfigFileFinderTomcat()
        result = config_file_finder_tomcat.check_call_command_in_container(
            "/",
            {
                "Config": {
                    "WorkingDir": ""
                }
            }
        )
        self.assertListEqual(result, [])

    def test_check_call_command_in_container(self):
        """
        The function to test the attempted extraction of the tomcatql.conf
        location from call commands.
        """
        with unittest.mock.patch(
                 'os.path.lexists',
                 new_callable = lambda: lambda x: True
             ), \
             unittest.mock.patch(
                 ("coguard_cli.image_check.config_file_finders.config_file_"
                  "finder_tomcat.ConfigFileFinderTomcat._create_temp_"
                  "location_and_mainfest_entry"),
                 new_callable=lambda: lambda a, b, c, d=None, e=None: ({"foo": "bar"}, "/etc/bar")
             ):
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            result = config_file_finder_tomcat.check_call_command_in_container(
                "/",
                {
                    "Config": {
                        "Cmd": [
                            "/bin/sh",
                            "-c",
                            "npm start --prefix $HOME_FOLDER/build"
                        ],
                        "WorkingDir": "",
                        "Entrypoint": [
                            "/docker-entrypoint.sh"
                        ],
                        "Env": [
                            "CATALINA_HOME=/usr/lib/tomcat"
                        ]
                    }
                }
            )
            self.assertEqual(result[0][0]["foo"], "bar")
            self.assertEqual(result[0][1], "/etc/bar")

    def test_extract_web_xmls_no_results(self):
        """
        Testing the function to extract web xmls
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("etc", [], ["bla.txt"])]):
            temp_location_tuple = ({
                "configFileList": []
            }, "/tmp/foo")
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            config_file_finder_tomcat._extract_web_xmls_and_context_xmls(
                "/",
                "/foo",
                temp_location_tuple
            )
            self.assertEqual(temp_location_tuple[0]["configFileList"], [])

    def test_extract_web_xmls_with_results(self):
        """
        Testing the function to extract web xmls
        """
        with unittest.mock.patch(
                 'os.path.lexists',
                 new_callable = lambda: lambda x: True
             ), \
             unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("/etc", [], ["web.xml"])]), \
             unittest.mock.patch(
                "os.makedirs",
                 new_callable=lambda: lambda location, exist_ok: None), \
             unittest.mock.patch(
                "shutil.copy"
             ):
            temp_location_tuple = ({
                "configFileList": []
            }, "/tmp/foo")
            config_file_finder_tomcat = ConfigFileFinderTomcat()
            config_file_finder_tomcat._extract_web_xmls_and_context_xmls(
                "/",
                "/foo",
                temp_location_tuple
            )
            self.assertEqual(temp_location_tuple[0]["configFileList"], [
                {'configFileType': 'xml',
                 'defaultFileName': 'web.xml',
                 'fileName': 'web.xml',
                 'subPath': 'etc'}
            ])

"""
The tests for the functions in __init__ of the config_file_finders module.
"""

import unittest
import unittest.mock
import coguard_cli.image_check.config_file_finders as cff_util

class TestCommonFunctionsConfigFileFinders(unittest.TestCase):
    """
    The test functions to check commpon functionality in test cases.
    """

    def test_copy_and_populate(self):
        """
        Testing the private function for correct functionality.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [("/", [], ["nginx.conf"])]), \
             unittest.mock.patch(
                 'shutil.copy'
             ), \
             unittest.mock.patch(
                 ("coguard_cli.image_check.config_file_finders."
                  "extract_include_directives")
             ), \
             unittest.mock.patch(
                 "tempfile.mkstemp",
                 new_callable=lambda: lambda dir: ("foo", "bar")
             ):
            current_manifest = {'complimentaryFileList': []}
            cff_util.copy_and_populate(
                "/",
                "/",
                "nginx.conf",
                False,
                "/tmp",
                current_manifest,
                "nginx",
                "include_foo",
                "include_foo"
            )
            self.assertEqual(len(current_manifest["complimentaryFileList"]), 1)

    def test_extract_include_directives(self):
        """
        Testing the extraction of include directives.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(read_data="include /etc/*.conf;")), \
             unittest.mock.patch(
                 ("coguard_cli.image_check.config_file_finders."
                  "copy_and_populate")
             ) as rec_call:
            current_manifest = {'complimentaryFileList': []}
            cff_util.extract_include_directives(
                '/',
                '/nginx.conf',
                '/tmp',
                current_manifest,
                'nginx',
                r'include\s+"?(.*?)"?\s*;'
            )
            rec_call.assert_called_once()

    def test_extract_include_directives_with_quotations(self):
        """
        Testing the extraction of include directives.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(read_data='include "/etc/*.conf;"')), \
             unittest.mock.patch(
                 ("coguard_cli.image_check.config_file_finders."
                  "copy_and_populate")
             ) as rec_call:
            current_manifest = {'complimentaryFileList': []}
            cff_util.extract_include_directives(
                '/',
                '/nginx.conf',
                '/tmp',
                current_manifest,
                'nginx',
                r'include\s+"?(.*?)"?\s*;'
            )
            rec_call.assert_called_once()

    def test_extract_include_directives_directory_with_quotations(self):
        """
        Testing the extraction of include directives.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(read_data='includedir "/etc/*.conf;"')), \
             unittest.mock.patch(
                 ("coguard_cli.image_check.config_file_finders."
                  "copy_and_populate")
             ) as rec_call:
            current_manifest = {'complimentaryFileList': []}
            cff_util.extract_include_directives(
                '/',
                '/nginx.conf',
                '/tmp',
                current_manifest,
                'nginx',
                r'include\s+"?(.*?)"?\s*;',
                r'includedir\s+"?(.*?)"?\s*;'
            )
            rec_call.assert_called_once()

    def test_adapt_match_to_actual_finds(self):
        """
        Basic functionality tests for "adapt_match_to_actual_finds".
        """
        self.assertIsNone(
            cff_util.adapt_match_to_actual_finds(
                "/etc/nginx.conf",
                False,
                "/opt/nginx.conf"
            )
        )
        self.assertEqual(
            cff_util.adapt_match_to_actual_finds(
                "../../nginx.conf.d/*.conf",
                False,
                "/tmp/foo/etc/nginx.conf.d/extra.conf"
            ),
            "../../nginx.conf.d/extra.conf"
        )
        self.assertEqual(
            cff_util.adapt_match_to_actual_finds(
                "/etc/mime.types",
                False,
                "/tmp/foo/etc/mime.types"
            ),
            "/etc/mime.types"
        )

    def test_get_path_behind_symlinks_recursed_too_often(self):
        """
        Should return None if too often recursed.
        """
        self.assertIsNone(cff_util.get_path_behind_symlinks(
            "foo",
            "bar",
            -1
        ))

    def test_get_path_behind_symlinks_not_link(self):
        """
        Should return the original call value.
        """
        with unittest.mock.patch(
                'os.path.islink',
                new_callable=lambda: lambda path_to_check: False
        ):
            self.assertEqual(cff_util.get_path_behind_symlinks(
                "foo",
                "bar"
            ), "bar")

    def test_get_path_behind_symlinks_link(self):
        """
        Should do one recursion
        """
        with unittest.mock.patch(
                'os.path.islink',
                new_callable=lambda: lambda path_to_check: path_to_check == "bar"
        ), unittest.mock.patch(
            'os.readlink',
            new_callable=lambda: lambda path_to_check: "baz"
        ):
            self.assertEqual(cff_util.get_path_behind_symlinks(
                "foo",
                "bar"
            ), "foo/baz")

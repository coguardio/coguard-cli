"""
The tests for the functions in __init__ of the config_file_finders module.
"""

import unittest
import unittest.mock
import coguard_cli.discovery.config_file_finders as cff_util

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
                 ("coguard_cli.discovery.config_file_finders."
                  "extract_include_directives")
             ), \
             unittest.mock.patch(
                 "tempfile.mkstemp",
                 new_callable=lambda: lambda dir: ("foo", "bar")
             ), \
             unittest.mock.patch(
                 'os.path.exists',
                 new_callable=lambda: lambda x: True
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

    def test_copy_and_populate_with_includedir(self):
        """
        Testing the private function for correct functionality.
        """
        with unittest.mock.patch(
                "os.walk",
                new_callable=lambda: lambda location: [
                    ("/include_foo",
                     [],
                     [
                         "nginx.conf",
                         "foo.conf"
                     ])]), \
             unittest.mock.patch(
                 'shutil.copy'
             ), \
             unittest.mock.patch(
                 ("coguard_cli.discovery.config_file_finders."
                  "extract_include_directives")
             ), \
             unittest.mock.patch(
                 "tempfile.mkstemp",
                 new_callable=lambda: lambda dir: ("foo", "bar")
             ), \
             unittest.mock.patch(
                 'os.path.exists',
                 new_callable=lambda: lambda x: True
             ):
            current_manifest = {'complimentaryFileList': []}
            cff_util.copy_and_populate(
                "/",
                "/",
                "include_foo",
                True,
                "/tmp",
                current_manifest,
                "nginx",
                "include_foo",
                "include_foo",
                "\\.conf"
            )
            self.assertEqual(len(current_manifest["complimentaryFileList"]), 2)

    def test_extract_include_directives(self):
        """
        Testing the extraction of include directives.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(read_data="include /etc/*.conf;")), \
             unittest.mock.patch(
                 ("coguard_cli.discovery.config_file_finders."
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
                 ("coguard_cli.discovery.config_file_finders."
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
                 ("coguard_cli.discovery.config_file_finders."
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
                 'os.makedirs'
             ), \
             unittest.mock.patch(
                 'shutil.copy'
             ), \
             unittest.mock.patch(
                 'os.path.exists',
                 new_callable=lambda: lambda x: True
             ):
            result = cff_util.create_temp_location_and_manifest_entry(
                '/',
                'Kubernetes',
                '/foo/Kubernetes',
                "kubernetes",
                "kubernetes",
                "yaml"
            )
            self.assertEqual(result[1], "/tmp/foo")
            self.assertEqual(result[0]["serviceName"], "kubernetes")

    def test_create_grouped_temp_locations_and_manifest_entries(self):
        """
        Testing the creation of temporary locations and manifest entries.
        """
        def new_callable(prefix="/tmp"):
            return "/tmp/foo"
        with unittest.mock.patch(
                'tempfile.mkdtemp',
                new_callable=lambda: new_callable), \
             unittest.mock.patch(
                 'os.makedirs'
             ), \
             unittest.mock.patch(
                 'shutil.copy'
             ):
            result = cff_util.create_grouped_temp_locations_and_manifest_entries(
                '/',
                {
                    "foo": [
                        "Kubernetes"
                    ]
                },
                "kubernetes",
                "kubernetes",
                "yaml"
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0][1], "/tmp/foo")
            self.assertEqual(result[0][0]["serviceName"], "kubernetes")

    def test_does_config_yaml_contain_required_keys(self):
        """
        Tests if a file is a proper kubernetes yaml file, heuristically.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(
                    read_data="receiversprocessorsexportersextensionsservice")):
            self.assertFalse(cff_util.does_config_yaml_contain_required_keys(
                "foo.txt",
                []
            ))

    def test_does_config_yaml_contain_required_keys_proper_not_kube(self):
        """
        Tests if a file is a proper kubernetes yaml file, heuristically.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(
                    read_data= "foo: bar")):
            self.assertFalse(cff_util.does_config_yaml_contain_required_keys(
                "foo.txt",
                [
                    "apiVersion",
                    "kind",
                    "metadata",
                    "spec"
                ]
            ))

    def test_does_config_yaml_contain_required_keys_proper_kube(self):
        """
        Tests if a file is a proper kubernetes yaml file, heuristically.
        """
        with unittest.mock.patch(
                'builtins.open',
                unittest.mock.mock_open(
                    read_data= \
                    """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  selector:
    matchLabels:
      app: nginx
  replicas: 2 # tells deployment to run 2 pods matching the template
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.14.2
        ports:
        - containerPort: 80
                    """)):
            self.assertTrue(cff_util.does_config_yaml_contain_required_keys(
                "foo.txt",
                [
                    "apiVersion",
                    "kind",
                    "metadata",
                    "spec"
                ]))

    def test_group_found_files_by_sub_path(self):
        """
        Testing the function to group found files by subpath.
        """
        path_to_file_system = "/etc"
        files = [
            "/etc/foo/bar/foo.txt",
            "/etc/foo/bar/bar.txt",
            "/etc/foo/bar/baz/biz/foo.txt",
            "/etc/foo/bor/boz/bez/biz.txt",
            "/etc/bla.txt"
        ]
        result = cff_util.group_found_files_by_subpath(
            path_to_file_system,
            files
        )
        expected_result = {
            "foo": [
                "/etc/foo/bar/foo.txt",
                "/etc/foo/bar/bar.txt",
                "/etc/foo/bar/baz/biz/foo.txt",
                "/etc/foo/bor/boz/bez/biz.txt"
            ],
            "": [
                "/etc/bla.txt"
            ]
        }
        self.assertListEqual(
            list(result.keys()),
            list(expected_result.keys())
        )
        for key_val in result:
            self.assertListEqual(result[key_val], expected_result[key_val])

    def test_amalgamate_keys(self):
        """
        Tests the amalgamation function.
        """
        input_dict = {
            "foo": [
                "/etc/foo/bar/foo.txt",
                "/etc/foo/bar/bar.txt"
            ],
            "foo/bar": [
                "/etc/foo/bar/baz/biz/foo.txt"
            ],
            "foo/bor": [
                "/etc/foo/bor/boz/bez/biz.txt"
            ],
            "": [
                "/etc/bla.txt"
            ]
        }
        expected_result = {
            "foo": [
                "/etc/foo/bar/foo.txt",
                "/etc/foo/bar/bar.txt",
                "/etc/foo/bar/baz/biz/foo.txt",
                "/etc/foo/bor/boz/bez/biz.txt"
            ],
            "": [
                "/etc/bla.txt"
            ]
        }
        result = cff_util._amalgamate_keys(input_dict)
        self.assertListEqual(
            list(result.keys()),
            list(expected_result.keys())
        )
        for key_val in result:
            self.assertListEqual(result[key_val], expected_result[key_val])

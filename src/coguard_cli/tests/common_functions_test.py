"""
This is the module containing checks for the common functions in the
CoGuard CLI module.
"""

import unittest
import unittest.mock
from io import StringIO
import coguard_cli

class TestCommonFunctions(unittest.TestCase):
    """
    The class to test the functions in coguard_cli.__init__
    """

    def print_failed_check_test(self):
        """
        Prints a failed check entry.
        """
        new_stdout = StringIO()
        with unittest.mock.patch(
                'sys.stdout',
                new_callable=lambda: new_stdout):
            coguard_cli.print_failed_check(coguard_cli.COLOR_RED, {
                "rule": {
                    "name": "foo_bar_baz",
                    "severity": 5,
                    "documentation": "Let's not even talk about it"
                }
            }, {})
            self.assertIn("not even talk", new_stdout.getvalue())

    def print_output_result_json_from_coguard_test(self):
        """
        Prints a failed check entry.
        """
        new_stdout = StringIO()
        result_json = {
            "failed": [
                {
                    "rule": {
                        "name": "kerberos_default_tgs_enctypes",
                        "severity": 3,
                        "documentation": "libdefaults has a key called \"default_tgs_enctypes\". If this value is set, custom cryptographic mechanisms are set instead of default secure ones. The value should only be set for legacy systems.\nSource: https://web.mit.edu/kerberos/krb5-1.12/doc/admin/conf_files/krb5_conf.html"
                    },
                    "machine": "us-jfk-001",
                    "service": "Kerberos"
                },
                {
                    "rule": {
                        "name": "kerberos_dns_lookup_kdc",
                        "severity": 1,
                        "documentation": "libdefaults has a key called \"dns_lookup_kdc\". If this value is set to true, the local DNS server is used to look up KDCs and other servers in the realm. Setting this value to true opens up a type of denial of service attack.\nSource: https://web.mit.edu/kerberos/krb5-1.12/doc/admin/conf_files/krb5_conf.html"
                    },
                    "machine": "us-jfk-001",
                    "service": "Kerberos"
                },
                {
                    "rule": {
                        "name": "nginx_server_tokens_off",
                        "severity": 2,
                        "documentation": "Knowing what NGINX version you are running may make you vulnerable if there is a known vulnerability for a specific version. There is a parameter to turn the display of the version on the error pages off. Our checking mechanism looks into each http-directive and ensures it is disabled on the top level.\nRemediation: Set `server_tokens` to `off` on the http-level of the configuration.\nSource: https://nginx.org/en/docs/http/ngx_http_core_module.html#server_tokens"
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                },
                {
                    "rule": {
                        "name": "nginx_one_root_outside_of_location_block",
                        "severity": 1,
                        "documentation": "One can define a root directory inside of a location block. However, one also needs a root directory for all directives that do not match any given location.\nRemediation: Either have a top-level root directive, or ensure that there is one in every `location` directive.\nSource: https://www.nginx.com/resources/wiki/start/topics/tutorials/config_pitfalls/"
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                },
                {
                    "rule": {
                        "name": "nginx_upstream_servers_https",
                        "severity": 4,
                        "documentation": "NGINX is popular to be used as load balancer. The communication to the upstream servers should exclusively be done via HTTPS, because otherwise there is unencrypted communication going on.\nRemediation: Every server in the upstream directive should be starting with `https://`."
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                },
                {
                    "rule": {
                        "name": "nginx_avoid_if_directives",
                        "severity": 1,
                        "documentation": "NGINX has an article called \"If is Evil\". Even though it is possible that there are uses where if makes sense, but in general, one should avoid using it.\nRemediation: Do not use the `if`-directive anywhere in your configuration file.\nSource: https://www.nginx.com/resources/wiki/start/topics/tutorials/config_pitfalls/\nhttps://www.nginx.com/resources/wiki/start/topics/depth/ifisevil/"
                    },
                    "machine": "us-jfk-001",
                    "service": "NGINX"
                }
            ]
        }
        with unittest.mock.patch(
                'sys.stdout',
                new_callable=lambda: new_stdout):
            coguard_cli.output_result_json_from_coguard(result_json, {})
            self.assertIn("1 High", new_stdout.getvalue())
            self.assertIn("1 Medium", new_stdout.getvalue())
            self.assertIn("4 Low", new_stdout.getvalue())

    def auth_token_retrieval_auth_config_not_none_test(self):
        """
        tests for the auth_token_retrieval.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.retrieve_configuration_object',
                new_callable=lambda: lambda arg_coguard_url, arg_auth_url: {}
        ), \
        unittest.mock.patch(
            'coguard_cli.auth.token.Token.authenticate_to_server',
            new_callable=lambda: lambda auth_config: "foo"
        ):
            token = coguard_cli.auth_token_retrieval("foo", "bar")
            self.assertIsNotNone(token)

    def auth_token_retrieval_auth_config_none_test(self):
        """
        tests for the auth_token_retrieval.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.retrieve_configuration_object',
                new_callable=lambda: lambda arg_coguard_url, arg_auth_url: "None"
        ), \
        unittest.mock.patch(
            'coguard_cli.auth.token.Token.authenticate_to_server',
            new_callable=lambda: lambda auth_config: "foo"
        ), \
        unittest.mock.patch(
            'coguard_cli.auth.sign_in_or_sign_up',
            new_callable=lambda: lambda coguard_api_url, coguard_auth_url: "foo"
        ):
            token = coguard_cli.auth_token_retrieval("foo", "bar")
            self.assertIsNotNone(token)

    def upload_and_evaluate_zip_candidate_zip_candidate_none_test(self):
        """
        Testing zip candidate None
        """
        new_stdout = StringIO()
        with unittest.mock.patch(
                'sys.stdout',
                new_callable=lambda: new_stdout):
            coguard_cli.upload_and_evaluate_zip_candidate(
                None,
                {},
                coguard_cli.auth.util.DealEnum.ENTERPRISE,
                "token",
                "https://portal.coguard.io/server",
                "foo",
                None,
                1,
                "foo"
            )
            self.assertIn("Unable to identify any known configuration files.", new_stdout.getvalue())

    def upload_and_evaluate_zip_candidate_test(self):
        """
        Testing zip candidate None
        """
        new_stdout = StringIO()
        with unittest.mock.patch(
                'coguard_cli.api_connection.send_zip_file_for_scanning',
                new_callable=lambda: lambda a, b, c, d, e, f: {"failed": []}), \
                unittest.mock.patch(
                    'sys.stdout',
                    new_callable=lambda: new_stdout), \
                unittest.mock.patch(
                'os.remove',
                new_callable=lambda: lambda a: None):
            auth_config = unittest.mock.MagicMock()
            auth_config.get_username = unittest.mock.Mock(return_value = "foo")
            coguard_cli.upload_and_evaluate_zip_candidate(
                ("foo.zip", {}),
                auth_config,
                coguard_cli.auth.util.DealEnum.ENTERPRISE,
                "token",
                "https://portal.coguard.io/server",
                "foo",
                "formatted",
                1,
                "foo"
            )
            self.assertIn("Scan result_jsons", new_stdout.getvalue())

    def upload_and_evaluate_zip_candidate_json_formatted_test(self):
        """
        Testing zip candidate None
        """
        new_stdout = StringIO()
        with unittest.mock.patch(
                'coguard_cli.api_connection.send_zip_file_for_scanning',
                new_callable=lambda: lambda a, b, c, d, e, f: {"failed": []}), \
                unittest.mock.patch(
                    'sys.stdout',
                    new_callable=lambda: new_stdout), \
                unittest.mock.patch(
                'os.remove',
                new_callable=lambda: lambda a: None):
            auth_config = unittest.mock.MagicMock()
            auth_config.get_username = unittest.mock.Mock(return_value = "foo")
            coguard_cli.upload_and_evaluate_zip_candidate(
                ("foo.zip", {}),
                auth_config,
                coguard_cli.auth.util.DealEnum.ENTERPRISE,
                "token",
                "https://portal.coguard.io/server",
                "foo",
                "json",
                1,
                "foo"
            )
            self.assertIn('{"failed": []}', new_stdout.getvalue())

    def extract_reference_string_test_empty_dicts(self):
        """
        A test of the extract reference string function.
        """
        self.assertEqual(coguard_cli.extract_reference_string(
            {}, {}
        ), "")

    def extract_reference_string_test_non_trivial_dicts(self):
        """
        A test of the extract reference string function.
        """
        self.assertEqual(coguard_cli.extract_reference_string(
            {"service": "foo"}, {
                "machines": {
                    "machine": {
                        "services": {
                            "foo": {
                                "configFileList": [
                                    {
                                        "subPath": "bar",
                                        "fileName": "foo.txt"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        ), " (affected files: bar/foo.txt for service foo)")

    def extract_reference_string_test_cluster_services_dicts(self):
        """
        A test of the extract reference string function.
        """
        self.assertEqual(coguard_cli.extract_reference_string(
            {"service": "foo"}, {
                "clusterServices": {
                    "foo": {
                        "configFileList": [
                            {
                                "subPath": "bar",
                                "fileName": "foo.txt"
                            }
                        ]
                    }
                }
            }
        ), " (affected files: bar/foo.txt for service foo)")

    def test_apply_fixes_to_folder(self):
        """
        Tests the apply_fixes_to_folder function.
        """
        inp_manifest = {
            "clusterServices": {
                "foo": {
                    "configFileList": [
                        {
                            "subPath": "bar",
                            "fileName": "foo.txt"
                        }
                    ]
                }
            },
            "machines": {
                "testMachine": {
                    "services": {
                        "testService": {
                            "configFileList": [
                                {
                                    "subPath": "./tmp",
                                    "fileName": "foo.ini"
                                }
                            ],
                            "complimentaryFileList": [
                                {
                                    "subPath": "./tmp",
                                    "fileName": "foo_c.ini"
                                }
                            ]
                        }
                    }
                }
            }
        }
        rm_tree = unittest.mock.Mock()
        copy_file = unittest.mock.Mock()
        with unittest.mock.patch(
                'os.path.exists',
                new_callable=lambda: lambda x: True
        ), \
        unittest.mock.patch(
            'shutil.copyfile',
            new_callable=lambda: copy_file
        ), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rm_tree
        ):
            coguard_cli.apply_fixes_to_folder("foo", "bar", inp_manifest)
            rm_tree.assert_called_once()
            self.assertEqual(copy_file.call_count, 3)
            copy_file.assert_any_call("foo/clusterServices/foo/bar/foo.txt", "bar/bar/foo.txt")

    def test_apply_fixes_to_folder_files_not_existing(self):
        """
        Tests the apply_fixes_to_folder function, but none of the files exist.
        """
        inp_manifest = {
            "clusterServices": {
                "foo": {
                    "configFileList": [
                        {
                            "subPath": "bar",
                            "fileName": "foo.txt"
                        }
                    ]
                }
            },
            "machines": {
                "testMachine": {
                    "services": {
                        "testService": {
                            "configFileList": [
                                {
                                    "subPath": "./tmp",
                                    "fileName": "foo.ini"
                                }
                            ],
                            "complimentaryFileList": [
                                {
                                    "subPath": "./tmp",
                                    "fileName": "foo_c.ini"
                                }
                            ]
                        }
                    }
                }
            }
        }
        rm_tree = unittest.mock.Mock()
        copy_file = unittest.mock.Mock()
        with unittest.mock.patch(
                'os.path.exists',
                new_callable=lambda: lambda x: False
        ), \
        unittest.mock.patch(
            'shutil.copyfile',
            new_callable=lambda: copy_file
        ), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rm_tree
        ):
            coguard_cli.apply_fixes_to_folder("foo", "bar", inp_manifest)
            self.assertEqual(rm_tree.call_count, 0)
            self.assertEqual(copy_file.call_count, 0)
            self.assertEqual(copy_file.call_count, 0)

    def test_apply_fixes_to_folder_os_error_copy(self):
        """
        Tests the apply_fixes_to_folder function.
        """
        inp_manifest = {
            "clusterServices": {
                "foo": {
                    "configFileList": [
                        {
                            "subPath": "bar",
                            "fileName": "foo.txt"
                        }
                    ]
                }
            },
            "machines": {
                "testMachine": {
                    "services": {
                        "testService": {
                            "configFileList": [
                                {
                                    "subPath": "./tmp",
                                    "fileName": "foo.ini"
                                }
                            ],
                            "complimentaryFileList": [
                                {
                                    "subPath": "./tmp",
                                    "fileName": "foo_c.ini"
                                }
                            ]
                        }
                    }
                }
            }
        }
        rm_tree = unittest.mock.Mock()
        def copy_file(x, y):
            raise OSError("foo")
        with unittest.mock.patch(
                'os.path.exists',
                new_callable=lambda: lambda x: True
        ), \
        unittest.mock.patch(
            'shutil.copyfile',
            new_callable=lambda: copy_file
        ), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rm_tree
        ):
            coguard_cli.apply_fixes_to_folder("foo", "bar", inp_manifest)
            self.assertEqual(rm_tree.call_count, 0)

    def test_upload_zip_candidate_fix_none(self):
        """
        Tests the and fix upload_zip_candidate function where the zip candidate is None
        """
        api_send = unittest.mock.Mock()
        mkdtemp = unittest.mock.Mock()
        apply_fixes_to_folder = unittest.mock.Mock()
        remove = unittest.mock.Mock()
        zipfile = unittest.mock.Mock(extractall=lambda x: None)
        with unittest.mock.patch(
                'coguard_cli.api_connection.send_zip_file_for_fixing',
                new_callable=api_send), \
             unittest.mock.patch(
                'coguard_cli.apply_fixes_to_folder',
                 new_callable=lambda: apply_fixes_to_folder), \
             unittest.mock.patch(
                'tempfile.mkdtemp',
                 new_callable=lambda: mkdtemp), \
             unittest.mock.patch(
                 'os.remove',
                 new_callable=lambda: remove), \
             unittest.mock.patch(
                'zipfile.ZipFile',
                 new_callable=lambda: zipfile):
            coguard_cli.upload_and_fix_zip_candidate(
                None,
                "foo",
                "token",
                "portal.coguard.io",
                "coguard"
            )
            self.assertEqual(mkdtemp.call_count, 0)
            self.assertEqual(remove.call_count, 0)
            self.assertEqual(zipfile.call_count, 0)
            self.assertEqual(apply_fixes_to_folder.call_count, 0)

    def test_upload_zip_candidate_fix_api_call_none(self):
        """
        Tests the upload and fix zip_candidate function
        """
        def api_send(a, b, c, d):
            return None
        mkdtemp = unittest.mock.Mock()
        remove = unittest.mock.Mock()
        apply_fixes_to_folder = unittest.mock.Mock()
        zipfile = unittest.mock.Mock(extractall=lambda x: None)
        zip_file_path = "foo"
        manifest = {"manifest": "rules"}
        with unittest.mock.patch(
                'coguard_cli.api_connection.send_zip_file_for_fixing',
                new_callable=lambda: api_send), \
             unittest.mock.patch(
                'coguard_cli.apply_fixes_to_folder',
                 new_callable=lambda: apply_fixes_to_folder), \
             unittest.mock.patch(
                'tempfile.mkdtemp',
                 new_callable=lambda: mkdtemp), \
             unittest.mock.patch(
                 'os.remove',
                 new_callable=lambda: remove), \
             unittest.mock.patch(
                'zipfile.ZipFile',
                 new_callable=lambda: zipfile):
            coguard_cli.upload_and_fix_zip_candidate(
                (zip_file_path, manifest),
                "foo",
                "token",
                "portal.coguard.io",
                "coguard"
            )
            self.assertEqual(mkdtemp.call_count, 0)
            self.assertEqual(remove.call_count, 1)
            self.assertEqual(zipfile.call_count, 0)
            self.assertEqual(apply_fixes_to_folder.call_count, 0)

    def test_upload_zip_candidate_fix(self):
        """
        Tests the upload and fix zip_candidate function
        """
        def api_send(a, b, c, d):
            return "result.zip"
        mkdtemp = unittest.mock.Mock()
        remove = unittest.mock.Mock()
        zip_file_path = "foo"
        extract_all = unittest.mock.Mock()
        apply_fixes_to_folder = unittest.mock.Mock()
        manifest = {"manifest": "rules"}
        with unittest.mock.patch(
                'coguard_cli.api_connection.send_zip_file_for_fixing',
                new_callable=lambda: api_send), \
             unittest.mock.patch(
                'coguard_cli.apply_fixes_to_folder',
                 new_callable=lambda: apply_fixes_to_folder), \
             unittest.mock.patch(
                'tempfile.mkdtemp',
                 new_callable=lambda: mkdtemp), \
             unittest.mock.patch(
                 'os.remove',
                 new_callable=lambda: remove), \
             unittest.mock.patch(
                 'zipfile.ZipFile.__init__',
                 new_callable = lambda: lambda x, y, z: None), \
            unittest.mock.patch(
                'zipfile.ZipFile.extractall',
                new_callable=lambda: extract_all):
            coguard_cli.upload_and_fix_zip_candidate(
                (zip_file_path, manifest),
                "foo",
                "token",
                "portal.coguard.io",
                "coguard"
            )
            self.assertEqual(mkdtemp.call_count, 1)
            self.assertEqual(remove.call_count, 2)
            self.assertEqual(extract_all.call_count, 1)
            self.assertEqual(apply_fixes_to_folder.call_count, 1)

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
            'coguard_cli.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            coguard_cli.perform_folder_fix(
                "foo",
                coguard_cli.auth.util.DealEnum.DEV,
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
            'coguard_cli.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            coguard_cli.perform_folder_fix(
                "foo",
                coguard_cli.auth.util.DealEnum.ENTERPRISE,
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
            'coguard_cli.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            coguard_cli.perform_folder_fix(
                "foo",
                coguard_cli.auth.util.DealEnum.ENTERPRISE,
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
            'coguard_cli.upload_and_fix_zip_candidate',
            new_callable=lambda: upload_and_fix), \
        unittest.mock.patch(
            'shutil.rmtree',
            new_callable=lambda: rmtree
        ):
            coguard_cli.perform_folder_fix(
                "foo",
                coguard_cli.auth.util.DealEnum.ENTERPRISE,
                "token",
                "coguard",
                "portal.coguard.io"
            )
            self.assertEqual(rmtree.call_count, 1)
            self.assertEqual(upload_and_fix.call_count, 1)

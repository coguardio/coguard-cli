"""
Testing module for the util.py section
"""

import unittest
import unittest.mock
from typing import Dict, Tuple
from io import StringIO
import pathlib

from coguard_cli import util
from coguard_cli import auth
from coguard_cli import print_colors

class TestUtilRoot(unittest.TestCase):
    """
    Unit testing the util functions of the util at the root of the project
    """

    def test_create_service_identifier_no_common_prefix(self):
        """
        Testing the service identifier creation.
        """
        service_instance = {
            "configFileList": [
                {
                    "subPath": "/foo"
                },
                {
                    "subPath": "/bar"
                }
            ]
        }
        currently_used_names = set()
        prefix = "bar"
        result = util.create_service_identifier(
            prefix,
            currently_used_names,
            service_instance
        )
        self.assertEqual(result, prefix)

    def test_create_service_identifier_already_existent(self):
        """
        Testing the service identifier creation.
        """
        service_instance = {
            "configFileList": [
                {
                    "subPath": "/foo"
                },
                {
                    "subPath": "/bar"
                }
            ]
        }
        currently_used_names = set(["bar"])
        prefix = "bar"
        result = util.create_service_identifier(
            prefix,
            currently_used_names,
            service_instance
        )
        self.assertEqual(result, f"{prefix}_0")

    def test_create_service_identifier_already_existent_multi_count(self):
        """
        Testing the service identifier creation.
        """
        service_instance = {
            "configFileList": [
                {
                    "subPath": "/foo"
                },
                {
                    "subPath": "/bar"
                }
            ]
        }
        currently_used_names = set(["bar"])
        prefix = "bar"
        result = util.create_service_identifier(
            prefix,
            currently_used_names,
            service_instance
        )
        self.assertEqual(result, f"{prefix}_0")
        result_after = util.create_service_identifier(
            prefix,
            currently_used_names,
            service_instance
        )
        self.assertEqual(result_after, f"{prefix}_1")

    def test_create_service_identifier_common_prefix(self):
        """
        Testing the service identifier creation.
        """
        service_instance = {
            "configFileList": [
                {
                    "subPath": "./foo/bar/boz"
                },
                {
                    "subPath": "./foo/bar/biz"
                }
            ]
        }
        currently_used_names = set(["bar"])
        prefix = "bar"
        result = util.create_service_identifier(
            prefix,
            currently_used_names,
            service_instance
        )
        self.assertEqual(result, f"{prefix}_foo_bar")

    def test_merge_coguard_infrastructure_description_folders_empty(self):
        """
        Test of `merge_coguard_infrastructure_description_folders` as described by the test name.
        """
        inp1 = ("foo", {})
        inp2 = ("bar", {})
        with unittest.mock.patch(
                "builtins.open",
                unittest.mock.mock_open()
        ) as open_mock:
            util.merge_coguard_infrastructure_description_folders(
                "prefix",
                inp1,
                inp2
            )
            open_mock.assert_called_once_with("foo/manifest.json", 'w', encoding="utf-8")

    def test_merge_coguard_infrastructure_description_folders_machines(self):
        """
        Test of `merge_coguard_infrastructure_description_folders` as described by the test name.
        """
        inp1 = ("foo", {})
        inp2 = ("bar", {
            "machines": {
                "bla": {
                    "id": "bla",
                    "services": {
                        "new_service": {
                            "version": "1"
                        }
                    }
                }
            }
        })
        mock_fd = unittest.mock.mock_open()
        with unittest.mock.patch(
                "builtins.open",
                mock_fd
        ) as open_mock, \
        unittest.mock.patch(
            "shutil.copytree"
        ) as shutil_mock, \
        unittest.mock.patch(
            "os.makedirs"
        ):
            util.merge_coguard_infrastructure_description_folders(
                "prefix",
                inp1,
                inp2
            )
            open_mock.assert_called_once_with("foo/manifest.json", 'w', encoding="utf-8")
            shutil_mock.assert_called_once_with(
                "bar/bla/new_service",
                "foo/bla/prefix_new_service",
                dirs_exist_ok=True
            )
            print(open_mock.mock_calls)
            handle = open_mock()
            handle.write.assert_any_call('"prefix_new_service"')

    def test_merge_coguard_infrastructure_description_folders_cluster(self):
        """
        Test of `merge_coguard_infrastructure_description_folders` as described by the test name.
        """
        inp1 = ("foo", {})
        inp2 = ("bar", {
            "clusterServices": {
                "new_service": {
                    "version": "1"
                }
            }
        })
        mock_fd = unittest.mock.mock_open()
        with unittest.mock.patch(
                "builtins.open",
                mock_fd
        ) as open_mock, \
        unittest.mock.patch(
            "shutil.copytree"
        ) as shutil_mock:
            util.merge_coguard_infrastructure_description_folders(
                "prefix",
                inp1,
                inp2
            )
            open_mock.assert_called_once_with("foo/manifest.json", 'w', encoding="utf-8")
            shutil_mock.assert_called_once_with(
                "bar/clusterServices/new_service",
                "foo/clusterServices/prefix_new_service",
                dirs_exist_ok=True
            )
            print(open_mock.mock_calls)
            handle = open_mock()
            handle.write.assert_any_call('"prefix_new_service"')

    def test_print_output_result_json_from_coguard(self):
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
                new_callable=lambda: new_stdout), \
             unittest.mock.patch(
                'coguard_cli.api_connection.get_fixable_rule_list',
                 new_callable=lambda: lambda token, coguard_api_url, user_name, organization: []):
            util.output_result_json_from_coguard(
                result_json,
                "foo",
                "bar",
                "baz",
                "boo"
            )
            self.assertIn("1 High", new_stdout.getvalue())
            self.assertIn("1 Medium", new_stdout.getvalue())
            self.assertIn("4 Low", new_stdout.getvalue())

    def test_upload_and_evaluate_zip_candidate_zip_candidate_none(self):
        """
        Testing zip candidate None
        """
        new_stdout = StringIO()
        with unittest.mock.patch(
                'sys.stdout',
                new_callable=lambda: new_stdout):
            util.upload_and_evaluate_zip_candidate(
                None,
                {},
                auth.enums.DealEnum.ENTERPRISE,
                "token",
                "https://portal.coguard.io/server",
                "foo",
                None,
                1,
                "foo",
                "iso"
            )
            self.assertIn("Unable to identify any known configuration files.", new_stdout.getvalue())

    def test_upload_and_evaluate_zip_candidate(self):
        """
        Testing zip candidate None
        """
        new_stdout = StringIO()
        with unittest.mock.patch(
                'coguard_cli.api_connection.send_zip_file_for_scanning',
                new_callable=lambda: lambda a, b, c, d, e, f, g: {"failed": []}), \
                unittest.mock.patch(
                    'sys.stdout',
                    new_callable=lambda: new_stdout), \
                unittest.mock.patch(
                'os.remove',
                new_callable=lambda: lambda a: None), \
                unittest.mock.patch(
                'coguard_cli.api_connection.get_fixable_rule_list',
                 new_callable=lambda: lambda token, coguard_api_url, user_name, organization: []), \
                unittest.mock.patch(
                'logging.debug',
                new_callable=unittest.mock.MagicMock()):
            auth_config = unittest.mock.MagicMock()
            auth_config.get_username = unittest.mock.Mock(return_value = "foo")
            util.upload_and_evaluate_zip_candidate(
                ("foo.zip", {}),
                auth_config,
                auth.enums.DealEnum.ENTERPRISE,
                "token",
                "https://portal.coguard.io/server",
                "foo",
                "formatted",
                1,
                "foo",
                "iso"
            )
            self.assertIn("SCANNING OF", new_stdout.getvalue())

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
            util.upload_and_evaluate_zip_candidate(
                ("foo.zip", {}),
                auth_config,
                auth.enums.DealEnum.ENTERPRISE,
                "token",
                "https://portal.coguard.io/server",
                "foo",
                "json",
                1,
                "foo",
                "iso"
            )
            self.assertIn('{"failed": []}', new_stdout.getvalue())

    def extract_reference_string_test_empty_dicts(self):
        """
        A test of the extract reference string function.
        """
        self.assertEqual(util.extract_reference_string(
            {}
        ), "")

    def extract_reference_string_test_non_trivial_dicts(self):
        """
        A test of the extract reference string function.
        """
        self.assertEqual(util.extract_reference_string(
            {"service": "foo",
             "fromLine": 0,
             "toLine": 1,
             "config_file": {
                 "fileName": "krb5.conf",
                 "subPath": ".",
                 "configFileType": "krb"
             }}
        ), " (affected files: ./krb5.conf)")

    def extract_reference_string_test_non_trivial_dicts_and_lines(self):
        """
        A test of the extract reference string function.
        """
        self.assertEqual(util.extract_reference_string(
            {"service": "foo",
             "fromLine": 2,
             "toLine": 5,
             "config_file": {
                 "fileName": "krb5.conf",
                 "subPath": ".",
                 "configFileType": "krb"
             }}
        ), " (affected files: ./krb5.conf, 2-5)")

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
            util.apply_fixes_to_folder("foo", "bar", inp_manifest)
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
            util.apply_fixes_to_folder("foo", "bar", inp_manifest)
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
            util.apply_fixes_to_folder("foo", "bar", inp_manifest)
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
                'coguard_cli.util.apply_fixes_to_folder',
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
            util.upload_and_fix_zip_candidate(
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
                'coguard_cli.util.apply_fixes_to_folder',
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
            util.upload_and_fix_zip_candidate(
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
                'coguard_cli.util.apply_fixes_to_folder',
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
            util.upload_and_fix_zip_candidate(
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

    def test_print_failed_check(self):
        """
        Prints a failed check entry.
        """
        new_stdout = StringIO()
        # Comment: we seem to also need to patch logging.debug
        #          since it seems to interfere with our mock on
        #          sys.stdout. Strange python behavior, and we might
        #          want to examine if this is a python bug.
        with unittest.mock.patch(
                'sys.stdout',
                new_callable=lambda: new_stdout), \
            unittest.mock.patch(
                'logging.debug',
                new_callable=unittest.mock.MagicMock()
            ):
            util.print_failed_check(print_colors.COLOR_RED, {
                "rule": {
                    "name": "foo_bar_baz",
                    "severity": 5,
                    "documentation": {
                        "documentation": "Let's not even talk about it",
                        "remediation": "foo",
                        "sources": []
                    }
                }
            }, {})
            self.assertIn("not even talk", new_stdout.getvalue())


    def test_merge_with_external_results(self):
        """
        Testing a proper scenario
        """
        with unittest.mock.patch(
                'builtins.open',
                new_callable=unittest.mock.mock_open
        ) as mock_file, \
        unittest.mock.patch(
                'os.mkdir'
        ), \
        unittest.mock.patch(
                'pathlib.Path.mkdir'
        ), \
        unittest.mock.patch(
            "json.dump"
        ) as mock_json_dump, \
        unittest.mock.patch(
            "shutil.copy2"
        ) as shutil_copy_2, \
        unittest.mock.patch(
            "shutil.copytree"
        ) as shutil_copytree, \
        unittest.mock.patch(
            "pathlib.Path.iterdir"
        ) as mock_iterdir, \
        unittest.mock.patch(
            "pathlib.Path.is_dir"
        ):
            coguard_folder_path = "/fake/coguard"
            manifest_dict = {}
            collected_tuple: Tuple[str, Dict] = (coguard_folder_path, manifest_dict)
            external_results = {
                "scannerA": "/fake/ext/scannerA",
                "scannerB": "/fake/ext/scannerB"
            }
            fake_dirs = [
                unittest.mock.MagicMock(spec=pathlib.Path, name='dir1'),
                unittest.mock.MagicMock(spec=pathlib.Path, name='file1')
            ]

            # Simulate one directory and one file
            mock_iterdir.side_effect = [fake_dirs, fake_dirs]  # Once per scanner
            fake_dirs[0].is_dir.return_value = True
            fake_dirs[1].is_dir.return_value = False

            util.merge_external_scan_results_with_final_folder(collected_tuple, external_results)

            # Check that "externalResults" got populated
            assert "externalResults" in collected_tuple[1]
            assert collected_tuple[1]["externalResults"] == ["scannerA", "scannerB"]

            # Check copytree and copy2 calls
            assert shutil_copytree.call_count == 2
            assert shutil_copy_2.call_count == 2

            # Check manifest.json was written
            mock_file.assert_called_once_with("/fake/coguard/manifest.json", "w", encoding="utf-8")
            mock_json_dump.assert_called_once()

    def test_merge_with_none_external_results(self):
        """
        Test None right away return.
        """
        with unittest.mock.patch(
                'builtins.open',
                new_callable=unittest.mock.mock_open
        ) as mock_file, \
        unittest.mock.patch(
            "json.dump"
        ) as mock_json_dump:
            collected_tuple = ("/fake/coguard", {})
            util.merge_external_scan_results_with_final_folder(collected_tuple, None)
            assert "externalResults" not in collected_tuple[1]
            mock_file.assert_not_called()
            mock_json_dump.assert_not_called()

    def test_merge_with_empty_external_results(self):
        """
        Test with empty external results.
        """
        with unittest.mock.patch(
                'builtins.open',
                new_callable=unittest.mock.mock_open
        ) as mock_file, \
        unittest.mock.patch(
            "json.dump"
        ) as mock_json_dump:
            collected_tuple = ("/fake/coguard", {})
            util.merge_external_scan_results_with_final_folder(collected_tuple, {})
            assert "externalResults" not in collected_tuple[1]
            mock_file.assert_not_called()
            mock_json_dump.assert_not_called()

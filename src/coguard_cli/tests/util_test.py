"""
Testing module for the util.py section
"""

import unittest
from coguard_cli import util


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

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

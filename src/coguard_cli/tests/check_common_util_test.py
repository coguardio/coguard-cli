"""
Tests for the functions in the check_common_util module.
"""

import unittest
from coguard_cli.check_common_util import replace_special_chars_with_underscore

class TestCheckCommonUtil(unittest.TestCase):
    """
    The class for testing the check_common_util module.
    """

    def test_replace_special_chars_with_underscore(self):
        """
        Every character other than a letter or a digit becomes an underscore,
        runs of underscores collapse, and leading and trailing ones are removed.
        """
        self.assertEqual(replace_special_chars_with_underscore("ozone-base-cluster"),
                         "ozone_base_cluster")
        self.assertEqual(replace_special_chars_with_underscore("../a  b//c_"),
                         "a_b_c")

    def test_replace_special_chars_with_underscore_keeps_zero(self):
        """
        `0` is a digit like any other, and is kept.
        """
        self.assertEqual(replace_special_chars_with_underscore("cluster0"),
                         "cluster0")
        self.assertEqual(replace_special_chars_with_underscore("nginx:1.20.0"),
                         "nginx_1_20_0")
        self.assertEqual(
            replace_special_chars_with_underscore("nginx:1.20.0 prod-10", True),
            "nginx_1_20_0 prod-10"
        )

    def test_replace_special_chars_with_underscore_keep_spaces(self):
        """
        With `keep_spaces`, spaces and dashes are kept as well.
        """
        self.assertEqual(
            replace_special_chars_with_underscore(" my cluster-1 / x ", True),
            "my cluster-1 _ x"
        )

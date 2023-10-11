"""
Testing module for the cluster_rule_fail_util.py module
"""

import unittest
from coguard_cli import cluster_rule_fail_util


class TestClusterRuleFailUtilRoot(unittest.TestCase):
    """
    Unit testing the util functions of the util at the root of the project
    """

    def test_is_ci_cd_there_existing_github_workflows(self):
        """
        Tests is_ci_cd_there with an existing github workflows folder.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable = lambda: lambda x: True
        ):
            additional_failed_rules = []
            result = cluster_rule_fail_util.is_ci_cd_there(".", additional_failed_rules)
            self.assertTrue(result)
            self.assertNotIn("cluster_no_ci_cd_tool_used", additional_failed_rules)

    def test_is_ci_cd_there_existing_jenkins(self):
        """
        Tests is_ci_cd_there with an existing Jenkins pipeline.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable = lambda: lambda x: False
        ), unittest.mock.patch(
                "os.walk",
                new_callable = lambda: lambda x: [([], [], ["foo.jenkinsfile"])]
        ):
            additional_failed_rules = []
            result = cluster_rule_fail_util.is_ci_cd_there(".", additional_failed_rules)
            self.assertTrue(result)
            self.assertNotIn("cluster_no_ci_cd_tool_used", additional_failed_rules)

    def test_is_ci_cd_there_existing_bitbucket_pipeline(self):
        """
        Tests is_ci_cd_there with an existing BitBucket pipeline.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable = lambda: lambda x: False
        ), unittest.mock.patch(
                "os.walk",
                new_callable = lambda: lambda x: [([], [], ["pipeline.yml"])]
        ):
            additional_failed_rules = []
            result = cluster_rule_fail_util.is_ci_cd_there(".", additional_failed_rules)
            self.assertTrue(result)
            self.assertNotIn("cluster_no_ci_cd_tool_used", additional_failed_rules)

    def test_is_ci_cd_there_existing_gitlab_pipeline(self):
        """
        Tests is_ci_cd_there with an existing GitLab pipeline.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable = lambda: lambda x: False
        ), unittest.mock.patch(
                "os.walk",
                new_callable = lambda: lambda x: [([], [], [".gitlab-ci.yml"])]
        ):
            additional_failed_rules = []
            result = cluster_rule_fail_util.is_ci_cd_there(".", additional_failed_rules)
            self.assertTrue(result)
            self.assertNotIn("cluster_no_ci_cd_tool_used", additional_failed_rules)

    def test_is_ci_cd_there_existing_circleci_pipeline(self):
        """
        Tests is_ci_cd_there with an existing circleci pipeline.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable = lambda: lambda x: x == "./.circleci"
        ), unittest.mock.patch(
                "os.walk",
                new_callable = lambda: lambda x: [([], [], [""])]
        ):
            additional_failed_rules = []
            result = cluster_rule_fail_util.is_ci_cd_there(".", additional_failed_rules)
            self.assertTrue(result)
            self.assertNotIn("cluster_no_ci_cd_tool_used", additional_failed_rules)

    def test_is_ci_cd_there_no_match(self):
        """
        Tests is_ci_cd_there with an existing circleci pipeline.
        """
        with unittest.mock.patch(
                "os.path.exists",
                new_callable = lambda: lambda x: False
        ), unittest.mock.patch(
                "os.walk",
                new_callable = lambda: lambda x: [([], [], [""])]
        ):
            additional_failed_rules = []
            result = cluster_rule_fail_util.is_ci_cd_there(".", additional_failed_rules)
            self.assertFalse(result)
            self.assertIn("cluster_no_ci_cd_tool_used", additional_failed_rules)

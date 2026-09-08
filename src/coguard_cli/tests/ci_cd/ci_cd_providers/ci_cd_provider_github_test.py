"""
This module contains tests for the GitHub Actions CI/CD provider
"""

import os
import shutil
import tempfile
import unittest
import unittest.mock
import yaml
from coguard_cli.ci_cd.ci_cd_providers.ci_cd_provider_github import CiCdProviderGitHub

class TestCiCdProviderGitHub(unittest.TestCase):
    """
    The test class for the CloudProviderFactory
    """

    def test_add_not_existent(self):
        """
        The generation of the CI/CD script.
        """
        with unittest.mock.patch(
                'pathlib.Path.mkdir'
        ) as mkdir_path, \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: True
        ):
            provider = CiCdProviderGitHub()
            return_val = provider.add("foo")
            self.assertIsNone(return_val)
            mkdir_path.assert_called_once()

    def test_add_existent(self):
        """
        The generation of the CI/CD script.
        """
        with unittest.mock.patch(
                'pathlib.Path.mkdir'
        ) as mkdir_path, \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: False
        ), \
        unittest.mock.patch(
            'pathlib.Path.write_bytes'
        ) as writer, \
        unittest.mock.patch(
            'pathlib.Path.read_bytes'
        ) as reader:
            provider = CiCdProviderGitHub()
            return_val = provider.add("foo")
            self.assertEqual(return_val, "foo/.github/workflows")
            self.assertIsNotNone(return_val)
            mkdir_path.assert_called_once()
            writer.assert_called_once()
            reader.assert_called_once()

    def test_add_cloudera(self):
        """
        The pipeline which scans a Cloudera cluster is written under a name of
        its own, so that it can live next to the one which scans the repository.
        """
        temp_dir = tempfile.mkdtemp(prefix="coguard-ci-cd-cloudera-test")
        try:
            provider = CiCdProviderGitHub()
            self.assertEqual(
                provider.add(temp_dir, "cloudera"),
                os.path.join(temp_dir, ".github", "workflows")
            )
            workflow = os.path.join(temp_dir, ".github", "workflows",
                                    "coguard_cloudera_gate.yml")
            self.assertTrue(os.path.exists(workflow))
            self.assertFalse(os.path.exists(os.path.join(
                temp_dir, ".github", "workflows", "coguard_scan.yml"
            )))
            with open(workflow, 'r', encoding='utf-8') as workflow_stream:
                content = workflow_stream.read()
            # The gate is only a gate if a finding fails the job, and the
            # credentials only stay out of the process list if they are handed
            # over through the environment.
            self.assertIn("--minimum-fail-level", content)
            self.assertIn("cloud cloudera", content)
            self.assertIn("CLOUDERA_MANAGER_PASSWORD:", content)
            self.assertNotIn("--cloudera-manager-password", content)
            # And it has to be a workflow GitHub can read.
            parsed = yaml.safe_load(content)
            self.assertIn("gate", parsed["jobs"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_add_unknown_cloud_provider(self):
        """
        A deployment there is no pipeline for yet is reported, rather than
        resulting in an empty workflow file.
        """
        with unittest.mock.patch(
                'pathlib.Path.mkdir'
        ) as mkdir_path:
            provider = CiCdProviderGitHub()
            self.assertIsNone(provider.add("foo", "aws"))
            mkdir_path.assert_not_called()

    def test_post_string(self):
        """
        The test of the post string.
        """
        provider = CiCdProviderGitHub()
        post_string = provider.post_string()
        self.assertIn("secrets.COGUARD_USER_NAME", post_string)

    def test_post_string_cloudera(self):
        """
        The reminder for the Cloudera pipeline names the secrets of Cloudera
        Manager as well, and says what kind of user belongs in them.
        """
        provider = CiCdProviderGitHub()
        post_string = provider.post_string("cloudera")
        self.assertIn("secrets.COGUARD_USER_NAME", post_string)
        self.assertIn("secrets.CLOUDERA_MANAGER_PASSWORD", post_string)
        self.assertIn("read-only", post_string)

    def test_get_identifier(self):
        """
        The test to get the identifier.
        """
        provider = CiCdProviderGitHub()
        identifier = provider.get_identifier()
        self.assertEqual(identifier, "github")

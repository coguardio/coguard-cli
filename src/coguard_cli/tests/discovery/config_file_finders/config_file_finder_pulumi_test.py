"""
Unit tests for pulumi discovery.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from coguard_cli.discovery.config_file_finders.config_file_finder_pulumi \
    import ConfigFileFinderPulumi


class TestConfigFileFinderPulumi(unittest.TestCase):
    """
    Unit tests for Pulumi discovery.
    """

    def setUp(self):
        self.finder = ConfigFileFinderPulumi()

    def test_extract_desired_resources(self):
        """
        Testing of extracting the desired resources when a preview is provided.
        """
        preview = {
            "steps": [
                {"op": "create", "urn": "urn1",
                 "newState": {"type": "aws:s3/bucket:Bucket", "inputs": {"name": "test"}}},
                {"op": "delete", "urn": "urn2",
                 "newState": {"type": "aws:ec2/vpc:Vpc"}},
                {"op": "update", "urn": "urn3",
                 "newState": {"type": "k8s:core/v1:Pod", "inputs": {}}},
            ]
        }

        result = self.finder._extract_desired_resources(preview)
        self.assertEqual(result, {
            "urn1": {"type": "aws:s3/bucket:Bucket", "inputs": {"name": "test"}},
            "urn3": {"type": "k8s:core/v1:Pod", "inputs": {}},
        })

    def test_merge_pulumi_state_helper_existing(self):
        """
        Testing the merging functionality for an existing resource.
        """
        old_state = {
            "deployment": {
                "resources": [
                    {"urn": "urn1", "type": "aws:s3/bucket:Bucket",
                     "inputs": {"old": True}, "outputs": {"id": "123"}},
                    {"urn": "stack", "type": "pulumi:pulumi:Stack",
                     "inputs": {}, "outputs": {}}
                ]
            }
        }

        desired = {
            "urn1": {"type": "aws:s3/bucket:Bucket", "inputs": {"name": "updated"}}
        }

        result = self.finder._merge_pulumi_state_helper(old_state, desired, deleted_urns=set())

        resources = {r["urn"]: r for r in result["deployment"]["resources"]}
        self.assertEqual(resources["urn1"]["inputs"], {"name": "updated"})
        self.assertEqual(resources["urn1"]["outputs"], {"id": "123"})
        self.assertEqual(resources["stack"]["type"], "pulumi:pulumi:Stack")

    def test_merge_pulumi_state_helper_new_resource(self):
        """
        Testing the merging functionality for a new resource.
        """
        old_state = {"deployment": {"resources": []}}
        desired = {"urn-new": {"type": "aws:s3/bucket:Bucket", "inputs": {}}}

        result = self.finder._merge_pulumi_state_helper(old_state, desired, set())

        self.assertEqual(result["deployment"]["resources"][0]["urn"], "urn-new")
        self.assertTrue(result["deployment"]["resources"][0]["custom"])

    def test_merge_pulumi_states(self):
        """
        General merge test for a pulumi state vs. stack.
        """
        stack = {
            "deployment": {
                "resources": [
                    {"urn": "urn-delete", "type": "aws:s3/bucket:Bucket", "inputs": {}, "outputs": {}}
                ]
            }
        }
        preview = {
            "steps": [
                {"op": "create", "urn": "urn-new",
                 "newState": {"type": "aws:lambda/function:Function", "inputs": {}}},
                {"op": "delete", "urn": "urn-delete"},
            ]
        }

        merged = self.finder._merge_pulumi_states(stack, preview)
        urns = {r["urn"] for r in merged["deployment"]["resources"]}

        self.assertIn("urn-new", urns)
        self.assertNotIn("urn-delete", urns)

    @patch("subprocess.run")
    def test_process_pulumi_project(self, mock_run):
        """
        Fully mock pulumi commands to avoid needing pulumi installed.
        """
        with tempfile.TemporaryDirectory() as tmp:
            pulumi_yaml = os.path.join(tmp, "Pulumi.yaml")
            with open(pulumi_yaml, "w") as f:
                f.write("name: test-project")

            # Mock pulumi CLI outputs
            def _mock_run(cmd, cwd, env, stdout, stderr, text, check):
                if cmd[:4] == ["pulumi", "stack", "ls", "--json"]:
                    return MagicMock(stdout="[]")
                elif cmd[:3] == ["pulumi", "stack", "init"]:
                    return MagicMock(stdout="")
                elif cmd[:3] == ["pulumi", "stack", "export"]:
                    return MagicMock(stdout=json.dumps({"deployment": {"resources": []}}))
                elif cmd[:4] == ["pulumi", "preview", "--non-interactive", "--json"]:
                    return MagicMock(stdout=json.dumps({"steps": []}))
                raise RuntimeError(f"Unexpected command: {cmd}")

            mock_run.side_effect = _mock_run

            output = self.finder._process_pulumi_project(tmp)

            self.assertIsNotNone(output)
            self.assertIn("deployment", output)

    def test_find_charts_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "nested", "dir"))
            p1 = os.path.join(tmp, "Pulumi.yaml")
            p2 = os.path.join(tmp, "nested", "dir", "Pulumi.yml")

            with open(p1, "w", encoding='utf-8') as f:
                f.write("name: test")
            with open(p2, "w", encoding='utf-8') as f:
                f.write("name: test-nested")

            result = self.finder._find_charts_files(tmp)
            self.assertEqual(set(result), {p1, p2})


    @patch.object(ConfigFileFinderPulumi, "_process_pulumi_project")
    def test_create_temp_location_and_manifest_entry(self, mock_proc):
        mock_proc.return_value = {
            "deployment": {"resources": [{"urn": "urn:example"}]}
        }

        with tempfile.TemporaryDirectory() as tmp:
            pulumi_yaml = os.path.join(tmp, "Pulumi.yaml")
            with open(pulumi_yaml, "w", encoding='utf-8') as f:
                f.write("name: test")

            result = self.finder._create_temp_location_and_manifest_entry(tmp, pulumi_yaml)
            self.assertIsNotNone(result)

            manifest, temp_location = result

            # Manifest correctness
            self.assertEqual(manifest["serviceName"], "pulumi")
            self.assertEqual(manifest["configFileList"][0]["fileName"], "ExportedPulumiStack.json")

            # The file should exist
            exported_file = os.path.join(temp_location, ".", "ExportedPulumiStack.json")
            self.assertTrue(os.path.isfile(exported_file))

            # Check that JSON written matches mock return
            with open(exported_file, "r", encoding='utf-8') as f:
                data = json.load(f)
            self.assertEqual(data, mock_proc.return_value)


    @patch.object(ConfigFileFinderPulumi, "_create_temp_location_and_manifest_entry")
    @patch.object(ConfigFileFinderPulumi, "_find_charts_files")
    def test_check_for_config_files_filesystem_search(self, mock_find, mock_create):
        mock_find.return_value = ["/fake/path/to/Pulumi.yaml"]
        mock_create.return_value = ({"serviceName": "pulumi"}, "/tmp/fake")

        result = self.finder.check_for_config_files_filesystem_search("/project")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ({"serviceName": "pulumi"}, "/tmp/fake"))
        mock_find.assert_called_once_with("/project")
        mock_create.assert_called_once()

    @patch("subprocess.run")
    def test_process_pulumi_project_pulumi_not_installed(self, mock_run):
        """Simulate Pulumi CLI not installed (FileNotFoundError)."""
        mock_run.side_effect = FileNotFoundError

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pulumi_yaml = os.path.join(tmp, "Pulumi.yaml")
            with open(pulumi_yaml, "w") as f:
                f.write("name: test")

            output = self.finder._process_pulumi_project(tmp)
            self.assertIsNone(output)

    @patch("subprocess.run")
    def test_process_pulumi_project_command_error(self, mock_run):
        """Simulate Pulumi CLI command failure (CalledProcessError)."""
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(returncode=1, cmd="pulumi stack ls --json")

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pulumi_yaml = os.path.join(tmp, "Pulumi.yaml")
            with open(pulumi_yaml, "w") as f:
                f.write("name: test")

            output = self.finder._process_pulumi_project(tmp)
            self.assertIsNone(output)

    @patch("subprocess.run")
    def test_process_pulumi_project_invalid_json(self, mock_run):
        """Simulate Pulumi returning invalid JSON."""
        mock_run.return_value = MagicMock(stdout="not-a-json")

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            pulumi_yaml = os.path.join(tmp, "Pulumi.yaml")
            with open(pulumi_yaml, "w") as f:
                f.write("name: test")

            output = self.finder._process_pulumi_project(tmp)
            self.assertIsNone(output)

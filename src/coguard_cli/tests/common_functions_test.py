"""
This is the module containing checks for the common functions in the
CoGuard CLI module.
"""

import unittest
import unittest.mock
import argparse
import subprocess
import coguard_cli

class TestCommonFunctions(unittest.TestCase):
    """
    The class to test the functions in coguard_cli.__init__
    """

    def test_auth_token_retrieval_auth_config_not_none(self):
        """
        tests for the auth_token_retrieval.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.util.retrieve_configuration_object',
                new_callable=lambda: lambda arg_coguard_url, arg_auth_url: {}
        ), \
        unittest.mock.patch(
            'coguard_cli.auth.token.Token.authenticate_to_server',
            new_callable=lambda: lambda auth_config: "foo"
        ):
            token = coguard_cli.auth_token_retrieval("foo", "bar")
            self.assertIsNotNone(token)

    def test_auth_token_retrieval_auth_config_none(self):
        """
        tests for the auth_token_retrieval.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.util.retrieve_configuration_object',
                new_callable=lambda: lambda arg_coguard_url, arg_auth_url: "None"
        ), \
        unittest.mock.patch(
            'coguard_cli.auth.token.Token.authenticate_to_server',
            new_callable=lambda: lambda auth_config: "foo"
        ), \
        unittest.mock.patch(
            'coguard_cli.auth.util.sign_in_or_sign_up',
            new_callable=lambda: lambda coguard_api_url, coguard_auth_url: "foo"
        ):
            token = coguard_cli.auth_token_retrieval("foo", "bar")
            self.assertIsNotNone(token)

    def test_output_format_validation_function(self):
        """
        Testing the validation function for the output-format parameter.
        """
        inp_str_1 = "formatted"
        self.assertEqual(inp_str_1, coguard_cli.validate_output_format(inp_str_1))
        inp_str_2 = "foo"
        with self.assertRaises(argparse.ArgumentTypeError):
            coguard_cli.validate_output_format(inp_str_2)
        inp_str_3 = "formatted,json"
        self.assertEqual(inp_str_3, coguard_cli.validate_output_format(inp_str_3))
        with self.assertRaises(argparse.ArgumentTypeError):
            coguard_cli.validate_output_format(
                ",".join([
                    inp_str_1,
                    inp_str_2,
                    inp_str_3
                ])
            )

    def test_clone_git_repo_fail_listdir_empty(self):
        """
        A test to clone a Git repo, with listdir being empty.
        """
        with unittest.mock.patch(
                'tempfile.mkdtemp',
                new_callable=lambda: lambda prefix: "/foo/bar"
        ), \
        unittest.mock.patch(
            'subprocess.run',
            new_callable=lambda: lambda *args, **kwargs: ""
        ), \
        unittest.mock.patch(
            'os.listdir',
            new_callable=lambda: lambda x: []
        ), \
        unittest.mock.patch(
            'os.path.isdir',
            new_callable=lambda: lambda x: True
        ):
            result = coguard_cli.clone_git_repo("foo")
            self.assertEqual(result, "")

    def test_clone_git_repo_fail_raise_exception(self):
        """
        A test to clone a Git repo, with listdir being empty.
        """
        def raise_error(*args, **kwargs):
            """
            Just raise a subprocesss error.
            """
            raise subprocess.CalledProcessError(returncode="1", cmd="foo")
        with unittest.mock.patch(
                'tempfile.mkdtemp',
                new_callable=lambda: lambda prefix: "/foo/bar"
        ), \
        unittest.mock.patch(
            'subprocess.run',
            new_callable=lambda: raise_error
        ), \
        unittest.mock.patch(
            'os.listdir',
            new_callable=lambda: lambda x: ["a"]
        ), \
        unittest.mock.patch(
            'os.path.isdir',
            new_callable=lambda: lambda x: True
        ):
            result = coguard_cli.clone_git_repo("foo")
            self.assertEqual(result, "")

    def test_clone_git_repo_pass(self):
        """
        A test to clone a Git repo, with listdir being empty.
        """
        with unittest.mock.patch(
                'tempfile.mkdtemp',
                new_callable=lambda: lambda prefix: "/foo/bar"
        ), \
        unittest.mock.patch(
            'subprocess.run',
            new_callable=lambda: lambda *args, **kwargs: ""
        ), \
        unittest.mock.patch(
            'os.listdir',
            new_callable=lambda: lambda x: ["a"]
        ), \
        unittest.mock.patch(
            'os.path.isdir',
            new_callable=lambda: lambda x: True
        ):
            result = coguard_cli.clone_git_repo("foo")
            self.assertEqual(result, "/foo/bar/a")

    @staticmethod
    def ci_cd_provider(identifier="github", added="/foo/.github/workflows"):
        """
        A CI/CD provider which records what it was asked to add.
        """
        provider = unittest.mock.MagicMock()
        provider.get_identifier.return_value = identifier
        provider.add.return_value = added
        provider.post_string.return_value = "remember your secrets"
        return provider

    def test_perform_ci_cd_action(self):
        """
        The pipeline of the repository itself is added without a cloud provider.
        """
        provider = self.ci_cd_provider()
        with unittest.mock.patch(
                'coguard_cli.ci_cd_provider_factory',
                new_callable=lambda: lambda: iter([provider])
        ), \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: True
        ):
            coguard_cli.perform_ci_cd_action("github", "add", "/foo")
            provider.add.assert_called_once_with("/foo", None)
            provider.post_string.assert_called_once_with(None)

    def test_perform_ci_cd_action_cloud_provider(self):
        """
        The requested deployment reaches the provider, so that the pipeline it
        writes is the one which scans that deployment.
        """
        provider = self.ci_cd_provider()
        with unittest.mock.patch(
                'coguard_cli.ci_cd_provider_factory',
                new_callable=lambda: lambda: iter([provider])
        ), \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: True
        ):
            coguard_cli.perform_ci_cd_action(
                "github", "add", "/foo", "cloudera"
            )
            provider.add.assert_called_once_with("/foo", "cloudera")
            provider.post_string.assert_called_once_with("cloudera")

    def test_perform_ci_cd_action_nothing_added(self):
        """
        A provider which could not add the pipeline results in a non-zero exit
        code, so that a pipeline which was meant to gate is never silently
        absent.
        """
        provider = self.ci_cd_provider(added=None)
        with unittest.mock.patch(
                'coguard_cli.ci_cd_provider_factory',
                new_callable=lambda: lambda: iter([provider])
        ), \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: True
        ):
            with self.assertRaises(SystemExit):
                coguard_cli.perform_ci_cd_action("github", "add", "/foo")

    def test_perform_ci_cd_action_unknown_provider(self):
        """
        A CI/CD provider which does not exist is an error.
        """
        with unittest.mock.patch(
                'coguard_cli.ci_cd_provider_factory',
                new_callable=lambda: lambda: iter([self.ci_cd_provider()])
        ), \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: True
        ):
            with self.assertRaises(SystemExit):
                coguard_cli.perform_ci_cd_action("gitlab", "add", "/foo")

    def test_perform_ci_cd_action_unknown_command(self):
        """
        A command other than `add` is an error.
        """
        with unittest.mock.patch(
                'coguard_cli.ci_cd_provider_factory',
                new_callable=lambda: lambda: iter([self.ci_cd_provider()])
        ), \
        unittest.mock.patch(
            'pathlib.Path.exists',
            new_callable=lambda: lambda y: True
        ):
            with self.assertRaises(SystemExit):
                coguard_cli.perform_ci_cd_action("github", "remove", "/foo")

    def test_perform_ci_cd_action_non_existent_folder(self):
        """
        A repository folder which does not exist is an error.
        """
        with unittest.mock.patch(
                'pathlib.Path.exists',
                new_callable=lambda: lambda y: False
        ):
            with self.assertRaises(SystemExit):
                coguard_cli.perform_ci_cd_action("github", "add", "/foo")

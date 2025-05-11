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

"""
Tests for the common functions in the coguard_cli.auth package.
"""

import os
import unittest
import unittest.mock
import requests
import coguard_cli.auth

class TestAuthClass(unittest.TestCase):
    """
    The class for testing the auth module.
    """

    def setUp(self):
        """
        Method to be run before all tests are being executed.
        """
        self.path_to_resources = "./coguard_cli/tests/auth/resources"

    def test_get_auth_file_non_existing_path(self):
        """
        Tests that the return value of get_auth_file is the empty dictionary
        if the path does not exist.
        """
        res = coguard_cli.auth.get_auth_file(
            os.path.join(
                self.path_to_resources, "I_WILL_NEVER_EXIST.json"
            )
        )
        self.assertDictEqual(res, {})

    def test_get_auth_file_existing_path(self):
        """
        Tests that the return value of get_auth_file represents the contents
        of the file if the path does exist.
        """
        res = coguard_cli.auth.get_auth_file(
            os.path.join(
                self.path_to_resources,
                "sample_config"
            )
        )
        self.assertDictEqual(res, {
            "password": "df28fd0e-58b0-416a-b659-cfeafdbef74a",
            "username": "email@email.com",
            "coguard-url": "https://portal.coguard.io"
        })

    def test_get_auth_file_existing_path_not_400(self):
        """
        Tests that the return value of get_auth_file represents the contents
        of the file if the path does exist.
        """
        res = coguard_cli.auth.get_auth_file(
            os.path.join(
                self.path_to_resources,
                "sample_config_not_400"
            )
        )
        self.assertDictEqual(res, {})

    def test_get_file_without_json(self):
        """
        Tests that the return value of get_auth_file is the empty dictionary
        if the contents of the file are not json
        """
        res = coguard_cli.auth.get_auth_file(
            os.path.join(
                self.path_to_resources,
                "sample_config_not_json"
            )
        )
        self.assertDictEqual(res, {})

    def test_retrieve_configuration_object_non_existing_path(self):
        """
        Tests that the return value of retrieve_configuration_object is the empty dictionary
        if the path does not exist.
        """
        res = coguard_cli.auth.retrieve_configuration_object(
            os.path.join(
                self.path_to_resources, "I_WILL_NEVER_EXIST.json"
            )
        )
        self.assertIsNone(res)

    def test_retrieve_configuration_object_existing_path(self):
        """
        Tests that the return value of retrieve_configuration_object represents the contents
        of the file if the path does exist.
        """
        res = coguard_cli.auth.retrieve_configuration_object(
            os.path.join(
                self.path_to_resources,
                "sample_config"
            )
        )
        self.assertIsNotNone(res)
        self.assertEqual(res.get_username(), "email@email.com")
        self.assertEqual(res.get_password(), "df28fd0e-58b0-416a-b659-cfeafdbef74a")
        self.assertEqual(res.get_coguard_url(), "https://portal.coguard.io")

    def test_get_config_object_without_json(self):
        """
        Tests that the return value of retrieve_configuration_object is the empty dictionary
        if the contents of the file are not json
        """
        res = coguard_cli.auth.retrieve_configuration_object(
            os.path.join(
                self.path_to_resources,
                "sample_config_not_json"
            )
        )
        self.assertIsNone(res)

    def test_authenticate_to_server_empty_config_object(self):
        """
        Tests that the authentication returns None if the configuration object is None
        """
        self.assertIsNone(coguard_cli.auth.authenticate_to_server(None))

    def test_authenticate_to_server_non_empty_config_object_404(self):
        """
        Tests that the authentication returns None if the status code
        is not 200.
        """
        config_obj = coguard_cli.auth.auth_config.CoGuardCliConfig("foo", "bar")
        def new_callable(url, data):
            response = requests.Response()
            setattr(response, 'status_code', 404)
            return response
        with unittest.mock.patch('requests.post',
                                 new_callable=lambda: new_callable):
            self.assertIsNone(coguard_cli.auth.authenticate_to_server(config_obj))

    def test_authenticate_to_server_non_empty_config_object_success(self):
        """
        Tests that the authentication returns None if the status code
        is not 200.
        """
        config_obj = coguard_cli.auth.auth_config.CoGuardCliConfig("foo", "bar")
        def new_callable(url, data):
            response = requests.Response()
            setattr(response, 'status_code', 200)
            return response
        def new_json(arg):
            return {
                "access_token": "foo"
            }
        with unittest.mock.patch('requests.post',
                                 new_callable=lambda: new_callable), \
             unittest.mock.patch('requests.Response.json',
                                 new_callable=lambda: new_json):
            result = coguard_cli.auth.authenticate_to_server(config_obj)
            self.assertIsNotNone(result)
            self.assertEqual(result, "foo")

    def test_store_config_object_in_auth_file(self):
        """
        Testing the storing of the configuration object
        """
        config_object = unittest.mock.Mock()
        makedirs_mock = unittest.mock.MagicMock()
        with unittest.mock.patch(
                'os.makedirs',
                makedirs_mock
        ), unittest.mock.patch(
            'os.chmod'
        ), unittest.mock.patch(
            'builtins.open',
            unittest.mock.mock_open()
        ):
            coguard_cli.auth.store_config_object_in_auth_file(
                config_object,
                "foo/bar/baz.conf"
            )
            makedirs_mock.assert_called_with("foo/bar", exist_ok=True)

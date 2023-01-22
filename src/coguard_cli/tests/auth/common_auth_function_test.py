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
        with unittest.mock.patch(
                'os.environ.get',
                new_callable=lambda: lambda x: None):
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
        with unittest.mock.patch(
                'os.environ.get',
                new_callable=lambda: lambda x: None):
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
        with unittest.mock.patch(
                'os.environ.get',
                new_callable=lambda: lambda x: None):
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
        def new_callable(url, data, timeout):
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
        def new_callable(url, data, timeout):
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

    def test_get_public_key_status_not_200(self):
        """
        Tests the public key extraction of the authentication server.
        """
        mock_response = unittest.mock.Mock(
            status_code = 420
        )
        mock_config_object = unittest.mock.Mock(
            get_auth_url = lambda: "https://portal.coguard.io"
        )
        with unittest.mock.patch('requests.get',
                                 new_callable=lambda: lambda url, timeout: mock_response):
            result = coguard_cli.auth.get_public_key(
                mock_config_object
            )
            self.assertIsNone(result)

    def test_get_public_key_status_200_no_public_key(self):
        """
        Tests the public key extraction of the authentication server.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: {}
        )
        mock_config_object = unittest.mock.Mock(
            get_auth_url = lambda: "https://portal.coguard.io/auth"
        )
        with unittest.mock.patch('requests.get',
                                 new_callable=lambda: lambda url, timeout: mock_response):
            result = coguard_cli.auth.get_public_key(
                mock_config_object
            )
            self.assertIsNone(result)

    def test_get_public_key_status_200_public_key(self):
        """
        Tests the public key extraction of the authentication server.
        """
        mock_response = unittest.mock.Mock(
            status_code = 200,
            json = lambda: {"public_key": "123456"}
        )
        mock_config_object = unittest.mock.Mock(
            get_auth_url = lambda: "https://portal.coguard.io/auth"
        )
        with unittest.mock.patch('requests.get',
                                 new_callable=lambda: lambda url, timeout: mock_response):
            result = coguard_cli.auth.get_public_key(
                mock_config_object
            )
            self.assertEqual(result, "123456")

    def test_get_decoded_jwt_token(self):
        """
        Tests the decoded jwt token.
        """
        mock_result = unittest.mock.Mock()
        mock_jwt = unittest.mock.Mock(
            decode = lambda token, public_key: mock_result
        )
        with unittest.mock.patch(
                'jwt.JWT',
                return_value=mock_jwt
        ), \
        unittest.mock.patch(
                'jwt.jwk_from_pem',
                new_callable = lambda: lambda b: "foo"
        ):
            result = coguard_cli.auth.get_decoded_jwt_token(
                "foo",
                "bar"
            )
            self.assertEqual(result, mock_result)

    def test_extract_organization_from_token_no_pk(self):
        """
        Tests the extraction of the organization key from the token.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.get_public_key',
                new_callable=lambda: lambda c: ""
        ):
            result = coguard_cli.auth.extract_organization_from_token(
                "foo", {}
            )
            self.assertIsNone(result)

    def test_extract_organization_from_token_pk_empty(self):
        """
        Tests the extraction of the organization key from the token.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.get_public_key',
                new_callable=lambda: lambda c: "pk"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.get_decoded_jwt_token',
                new_callable=lambda: lambda token, public_key: {}
        ):
            result = coguard_cli.auth.extract_organization_from_token(
                "foo", {}
            )
            self.assertIsNone(result)

    def test_extract_organization_from_token_pk(self):
        """
        Tests the extraction of the organization key from the token.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.get_public_key',
                new_callable=lambda: lambda c: "pk"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.get_decoded_jwt_token',
                new_callable=lambda: lambda token, public_key: {"organization": "bar"}
        ):
            result = coguard_cli.auth.extract_organization_from_token(
                "foo", {}
            )
            self.assertEqual(result, "bar")

    def test_extract_deal_type_from_token_no_pk(self):
        """
        Tests the extraction of deal type from the token no public key.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.get_public_key',
                new_callable=lambda: lambda c: ""
        ):
            result = coguard_cli.auth.extract_deal_type_from_token(
                "foo", {}
            )
            self.assertEqual(result, coguard_cli.auth.DealEnum.FREE)

    def test_extract_deal_type_from_token_pk_no_deal_id(self):
        """
        Tests the extraction of deal type from the token no public key.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.get_public_key',
                new_callable=lambda: lambda c: "foo"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.get_decoded_jwt_token',
                new_callable=lambda: lambda token, pk: {}
        ):
            result = coguard_cli.auth.extract_deal_type_from_token(
                "foo", {}
            )
            self.assertEqual(result, coguard_cli.auth.DealEnum.FREE)

    def test_extract_deal_type_from_token_pk_deal_id(self):
        """
        Tests the extraction of deal type from the token no public key.
        """
        with unittest.mock.patch(
                'coguard_cli.auth.get_public_key',
                new_callable=lambda: lambda c: "foo"
        ), \
        unittest.mock.patch(
                'coguard_cli.auth.get_decoded_jwt_token',
                new_callable=lambda: lambda token, pk: {
                    "realm_access": {
                        "roles": [
                            "DEV"
                        ]
                    }
                }):
            result = coguard_cli.auth.extract_deal_type_from_token(
                "foo", {}
            )
            self.assertEqual(result, coguard_cli.auth.DealEnum.DEV)
